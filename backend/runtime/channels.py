import os
import json
import asyncio
import datetime
import time
import httpx
from typing import Optional, Callable
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from sqlmodel import Session, select
from backend.db.database import engine
from backend.db.models import Workflow, WorkflowRun, Message, AgentMemory, SystemSetting, UserSessionState, Schedule
from backend.runtime.scheduler import add_or_update_schedule_job

# We will initialize global variables for telegram bot
telegram_bot_app: Optional[Application] = None
global_broadcast_callback: Optional[Callable] = None


async def send_telegram_message(chat_id: str, text: str) -> bool:
    """Send a message to a Telegram chat via the running bot, chunking long text.

    Used for outbound (non-reply) delivery such as scheduled workflow runs where
    there is no inbound Update object to reply to. Returns True on success.
    """
    if not telegram_bot_app:
        print("[Telegram] Cannot send message: bot is not running.")
        return False
    if not chat_id:
        return False
    try:
        bot = telegram_bot_app.bot
        # Telegram hard limit is 4096 chars; chunk at 4000 to be safe
        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                await bot.send_message(chat_id=chat_id, text=text[i:i + 4000])
        else:
            await bot.send_message(chat_id=chat_id, text=text)
        return True
    except Exception as e:
        print(f"[Telegram] Failed to send message to chat {chat_id}: {str(e)}")
        return False

# 1. Telegram long-polling bot setup
async def start_telegram_bot(broadcast_callback: Optional[Callable] = None):
    """Start Telegram bot using long polling in an asynchronous task."""
    global telegram_bot_app, global_broadcast_callback
    global_broadcast_callback = broadcast_callback
    
    # Try fetching from DB first
    token = None
    try:
        with Session(engine) as db:
            setting = db.exec(select(SystemSetting).where(SystemSetting.key == "TELEGRAM_BOT_TOKEN")).first()
            if setting and setting.value:
                token = setting.value
    except Exception as e:
        print(f"[Telegram] Failed to fetch token from DB: {e}")
        
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN":
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN":
        print("[WARNING] TELEGRAM_BOT_TOKEN is not set or left as default. Telegram bot will not start.")
        return
        
    try:
        # Build python-telegram-bot application
        app = Application.builder().token(token).build()
        
        # Add basic command handlers
        app.add_handler(CommandHandler("start", telegram_start_handler))
        app.add_handler(CommandHandler("help", telegram_help_handler))
        app.add_handler(CommandHandler("reset", telegram_reset_handler))
        app.add_handler(CommandHandler("agent", telegram_agent_handler))
        app.add_handler(CommandHandler("my_schedules", telegram_my_schedules_handler))
        app.add_handler(CommandHandler("enable_schedule", telegram_enable_schedule_handler))
        app.add_handler(CommandHandler("disable_schedule", telegram_disable_schedule_handler))
        
        # Handle all text messages (non-commands)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_message_handler))
        
        # Initialize and start bot polling
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        telegram_bot_app = app
        print(f"Telegram bot successfully started and polling.")
    except Exception as e:
        print(f"[ERROR] Failed to start Telegram bot: {str(e)}")

async def stop_telegram_bot():
    """Safely shut down the Telegram bot polling process."""
    global telegram_bot_app
    if telegram_bot_app:
        try:
            await telegram_bot_app.updater.stop()
            await telegram_bot_app.stop()
            await telegram_bot_app.shutdown()
            print("Telegram bot polling stopped.")
            telegram_bot_app = None
        except Exception as e:
            print(f"Error stopping Telegram bot: {str(e)}")

async def reload_telegram_bot(token: str):
    """Safely shut down the old bot instance and start a new one with the updated token."""
    global telegram_bot_app, global_broadcast_callback
    print(f"[Telegram] Reloading Telegram Bot with new token...")
    await stop_telegram_bot()
    await asyncio.sleep(1.0)
    await start_telegram_bot(broadcast_callback=global_broadcast_callback)

# Telegram Handlers
async def telegram_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respond to start command, listing available workflows."""
    chat_id = str(update.effective_chat.id)
    welcome_text = (
        "👋 Welcome to the Yuno AI Bot! Get started with /help for more details.\n\n"
        f"🆔 Your Chat ID is `{chat_id}` — paste this into the Web UI's schedule form "
        "to receive scheduled workflow runs right here."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def telegram_help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "💡 **Available Commands:**\n\n"
        "/start — Welcome message & bot intro\n"
        "/agent — List active workflows & select one\n"
        "/reset — Clear chat history for current workflow\n"
        "/my\\_schedules — View all registered cron schedules\n"
        "/enable\\_schedule `<id>` — Enable a paused schedule\n"
        "/disable\\_schedule `<id>` — Disable an active schedule\n"
        "/help — Show this command listing\n\n"
        "💬 **Tip:** After selecting a workflow with /agent, just type "
        "your message normally to interact with the agents!"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def telegram_reset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear message history and persistent memories/facts for the user's currently active workflow only."""
    chat_id = str(update.effective_chat.id)
    print(f"[Telegram] Resetting session for chat_id: {chat_id}")
    
    with Session(engine) as db:
        # Find the user's currently active workflow
        user_state = db.get(UserSessionState, chat_id)
        if not user_state or not user_state.active_workflow_id:
            await update.message.reply_text(
                "❌ No active workflow linked to your session.\n"
                "Use `/agent` to select a workflow first, then `/reset` to clear its context."
            )
            return
        
        active_wf_id = user_state.active_workflow_id
        scoped_session_id = f"{chat_id}_wf{active_wf_id}"
        
        # Get workflow name for the response message
        wf = db.get(Workflow, active_wf_id)
        wf_name = wf.name if wf else f"Workflow #{active_wf_id}"
        
        # Delete message history for the scoped session only
        msgs = db.exec(select(Message).where(Message.session_id == scoped_session_id)).all()
        deleted_msgs = len(msgs)
        for msg in msgs:
            db.delete(msg)
        
        # Delete persistent memories for the scoped session only
        memories = db.exec(select(AgentMemory).where(AgentMemory.session_id == scoped_session_id)).all()
        deleted_memories = len(memories)
        for mem in memories:
            db.delete(mem)
        
        # Suffix old WorkflowRun session_ids to reset cumulative stats
        reset_suffix = f"_reset_{int(time.time())}"
        runs = db.exec(select(WorkflowRun).where(WorkflowRun.session_id == scoped_session_id)).all()
        for run in runs:
            run.session_id = f"{scoped_session_id}{reset_suffix}"
            db.add(run)
        
        db.commit()
    
    response_text = (
        "🧹 **Session Reset Successful!**\n\n"
        f"Workflow: **{wf_name}**\n"
        f"• Cleared **{deleted_msgs}** chat history messages.\n"
        f"• Cleared **{deleted_memories}** long-term memory facts.\n\n"
        "Your next message to this workflow will start fresh!"
    )
    await update.message.reply_text(response_text, parse_mode="Markdown")

async def telegram_agent_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all available workflows and allow selecting one by typing /agent [number]."""
    chat_id = str(update.effective_chat.id)
    
    with Session(engine) as db:
        workflows = db.exec(select(Workflow).where(Workflow.is_active == True)).all()
        
    if not workflows:
        await update.message.reply_text("❌ No active workflows configured in the system.")
        return
        
    # Check if user passed the argument directly, e.g., /agent 2
    if context.args:
        try:
            choice = int(context.args[0])
            if 1 <= choice <= len(workflows):
                selected_wf = workflows[choice - 1]
                with Session(engine) as db:
                    state_rec = db.get(UserSessionState, chat_id)
                    if state_rec:
                        state_rec.active_workflow_id = selected_wf.id
                        state_rec.updated_at = datetime.datetime.utcnow()
                    else:
                        state_rec = UserSessionState(chat_id=chat_id, active_workflow_id=selected_wf.id)
                    db.add(state_rec)
                    db.commit()
                await update.message.reply_text(
                    f"🔗 **Connected to workflow:**\n"
                    f"👉 **{selected_wf.name}**\n\n"
                    f"All your future messages will be handled by this workflow. "
                    f"Run `/reset` to clear this connection or select another agent using `/agent`.",
                    parse_mode="Markdown"
                )
                return
        except ValueError:
            pass
            
    # List workflows
    list_lines = ["🤖 **Available Agent Workflows:**\n"]
    for idx, wf in enumerate(workflows):
        list_lines.append(f"[{idx + 1}] **{wf.name}**\n   _{wf.description or 'No description.'}_\n")
        
    list_lines.append("\n👉 To connect, reply with the number (e.g. `2`) or type `/agent [number]`.")
    await update.message.reply_text("\n".join(list_lines), parse_mode="Markdown")

async def telegram_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route incoming Telegram chat messages to the active workflow containing a Telegram trigger."""
    chat_id = str(update.effective_chat.id)
    user_name = update.effective_user.first_name
    input_text = update.message.text.strip()
    
    print(f"[Telegram] Received message from {user_name} (ID: {chat_id}): '{input_text}'")
    
    # Import execution workflow here to avoid circular imports
    from backend.runtime.executor import execute_workflow
    
    # Check if user is choosing a workflow by replying with a number
    with Session(engine) as db:
        active_workflows = db.exec(select(Workflow).where(Workflow.is_active == True)).all()
        
    try:
        # Check if the input is a single integer
        choice = int(input_text)
        if 1 <= choice <= len(active_workflows):
            selected_wf = active_workflows[choice - 1]
            with Session(engine) as db:
                state_rec = db.get(UserSessionState, chat_id)
                if state_rec:
                    state_rec.active_workflow_id = selected_wf.id
                    state_rec.updated_at = datetime.datetime.utcnow()
                else:
                    state_rec = UserSessionState(chat_id=chat_id, active_workflow_id=selected_wf.id)
                db.add(state_rec)
                db.commit()
            await update.message.reply_text(
                f"🔗 **Connected to workflow:**\n"
                f"👉 **{selected_wf.name}**\n\n"
                f"All your future messages will be handled by this workflow. "
                f"Run `/reset` to clear this connection or select another agent using `/agent`.",
                parse_mode="Markdown"
            )
            return
    except ValueError:
        pass
        
    # Check if there is a linked active workflow for this user in UserSessionState
    workflow_id = None
    with Session(engine) as db:
        user_state = db.get(UserSessionState, chat_id)
        if user_state and user_state.active_workflow_id:
            # Verify the workflow exists and is active
            target_wf = db.get(Workflow, user_state.active_workflow_id)
            if target_wf and target_wf.is_active:
                workflow_id = target_wf.id
            else:
                # Connected workflow was deleted or deactivated, clear connection
                user_state.active_workflow_id = None
                db.add(user_state)
                db.commit()
                await update.message.reply_text(
                    "⚠️ The workflow you were previously connected to has been deleted or deactivated. "
                    "Please select a new workflow using `/agent`."
                )
                return
                
        # If no user-specific workflow linked, fall back to default Telegram trigger workflow
        if not workflow_id:
            for wf in active_workflows:
                nodes = json.loads(wf.nodes_json)
                for node in nodes:
                    if node.get("type") == "trigger" and node.get("data", {}).get("trigger_source") == "telegram":
                        workflow_id = wf.id
                        break
                if workflow_id:
                    break
                    
    if not workflow_id:
        await update.message.reply_text(
            "❌ No active workflow connected to your chat session. "
            "Please select one using `/agent` or make sure you have an active workflow "
            "with a Telegram Trigger configured in the visual Web UI."
        )
        return
        
    # Inform user that agents are running
    # Show a dynamic "thinking" indicator that cycles phrases + a typing action
    # until the workflow produces its result, so the user isn't staring at a static message.
    status_msg = await update.message.reply_text("🤔 Analyzing your request...")
    thinking_phrases = [
        "🤔 Analyzing your request...",
        "🧠 Agents are collaborating...",
        "🔎 Gathering information...",
        "⚙️ Working through the steps...",
        "✍️ Composing a response...",
    ]
    target_chat = update.effective_chat.id

    async def animate_thinking():
        idx = 0
        try:
            while True:
                try:
                    await context.bot.send_chat_action(chat_id=target_chat, action=ChatAction.TYPING)
                except Exception:
                    pass
                await asyncio.sleep(3)
                idx = (idx + 1) % len(thinking_phrases)
                try:
                    await context.bot.edit_message_text(
                        chat_id=target_chat,
                        message_id=status_msg.message_id,
                        text=thinking_phrases[idx],
                    )
                except Exception:
                    # Ignore "message is not modified" and transient edit errors
                    pass
        except asyncio.CancelledError:
            pass

    animation_task = asyncio.create_task(animate_thinking())

    try:
        metadata = {"chat_id": chat_id, "user_name": user_name, "message_id": update.message.message_id}

        # Execute workflow with per-workflow scoped session ID
        scoped_session_id = f"{chat_id}_wf{workflow_id}"
        response_text = await execute_workflow(
            workflow_id=workflow_id,
            input_message=input_text,
            trigger_source="telegram",
            session_id=scoped_session_id,
            trigger_metadata=metadata,
            broadcast_callback=global_broadcast_callback
        )
    except Exception as e:
        response_text = f"⚠️ Error running agent workflow: {str(e)}"
    finally:
        # Stop the animation and remove the status message before sending the result
        animation_task.cancel()
        await asyncio.gather(animation_task, return_exceptions=True)
        try:
            await status_msg.delete()
        except Exception:
            pass

    # Send response back to Telegram chat
    # Split text if it is too long (Telegram limit is 4096 chars)
    if len(response_text) > 4000:
        for i in range(0, len(response_text), 4000):
            await update.message.reply_text(response_text[i:i+4000])
    else:
        await update.message.reply_text(response_text)


# Telegram Schedule Management Commands

async def telegram_my_schedules_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all registered cron schedules with their status."""
    with Session(engine) as db:
        schedules = db.exec(select(Schedule)).all()
        if not schedules:
            await update.message.reply_text("📅 No schedules configured. Create them from the Web UI.")
            return
        
        lines = ["📅 **Registered Schedules:**\n"]
        for idx, sch in enumerate(schedules):
            wf = db.get(Workflow, sch.workflow_id)
            wf_name = wf.name if wf else f"Workflow #{sch.workflow_id}"
            status = "🟢 Active" if sch.is_active else "🔴 Inactive"
            lines.append(
                f"{idx + 1}. ID `#{sch.id}` — {sch.name}\n"
                f"   Workflow: {wf_name}\n"
                f"   Cron: `{sch.cron_expression}`\n"
                f"   Status: {status}\n"
            )
        
        lines.append("💡 Use `/enable_schedule <id>` or `/disable_schedule <id>` to toggle.")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def telegram_enable_schedule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable a paused cron schedule by ID."""
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/enable_schedule <id>`\nExample: `/enable_schedule 1`", parse_mode="Markdown")
        return
    
    try:
        schedule_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Invalid schedule ID. Must be a number.")
        return
    
    with Session(engine) as db:
        sch = db.get(Schedule, schedule_id)
        if not sch:
            await update.message.reply_text(f"❌ Schedule #{schedule_id} not found.")
            return
        
        if sch.is_active:
            await update.message.reply_text(f"ℹ️ Schedule #{schedule_id} is already active.")
            return
        
        sch.is_active = True
        db.add(sch)
        db.commit()
    
    await add_or_update_schedule_job(schedule_id)
    await update.message.reply_text(f"✅ Schedule `#{schedule_id}` enabled. Cron job is now active.", parse_mode="Markdown")


async def telegram_disable_schedule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable an active cron schedule by ID."""
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/disable_schedule <id>`\nExample: `/disable_schedule 1`", parse_mode="Markdown")
        return
    
    try:
        schedule_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Invalid schedule ID. Must be a number.")
        return
    
    with Session(engine) as db:
        sch = db.get(Schedule, schedule_id)
        if not sch:
            await update.message.reply_text(f"❌ Schedule #{schedule_id} not found.")
            return
        
        if not sch.is_active:
            await update.message.reply_text(f"ℹ️ Schedule #{schedule_id} is already inactive.")
            return
        
        sch.is_active = False
        db.add(sch)
        db.commit()
    
    await add_or_update_schedule_job(schedule_id)
    await update.message.reply_text(f"⏸️ Schedule `#{schedule_id}` disabled. Cron job paused.", parse_mode="Markdown")


# 2. Slack and WhatsApp Webhook Handlers
# These are helper functions called from FastAPI endpoints to run workflows asynchronously.

async def handle_slack_webhook(payload: dict, broadcast_callback: Optional[Callable] = None) -> dict:
    """Process incoming Slack webhook events, matching them to an active Slack workflow."""
    # Slack URL Verification Challenge
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}
        
    event = payload.get("event", {})
    # Ignore messages sent by bots (including ourselves) to avoid loops
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return {"status": "ignored_bot"}
        
    text = event.get("text", "")
    channel_id = event.get("channel", "")
    user_id = event.get("user", "")
    
    if not text or not channel_id:
        return {"status": "invalid_event"}
        
    # Find active workflow with a Slack Trigger
    workflow_id = None
    with Session(engine) as db:
        workflows = db.exec(select(Workflow).where(Workflow.is_active == True)).all()
        for wf in workflows:
            nodes = json.loads(wf.nodes_json)
            for node in nodes:
                if node.get("type") == "trigger" and node.get("data", {}).get("trigger_source") == "slack":
                    workflow_id = wf.id
                    break
            if workflow_id:
                break
                
    if not workflow_id:
        print("[Slack] No active workflow configured with a Slack Trigger.")
        return {"status": "no_active_workflow"}
        
    # Run the workflow execution in the background asynchronously
    asyncio.create_task(run_slack_workflow_async(
        workflow_id=workflow_id,
        input_text=text,
        channel_id=channel_id,
        user_id=user_id,
        broadcast_callback=broadcast_callback
    ))
    
    return {"status": "triggered"}

async def run_slack_workflow_async(
    workflow_id: int, 
    input_text: str, 
    channel_id: str, 
    user_id: str,
    broadcast_callback: Optional[Callable] = None
):
    """Execute Slack workflow asynchronously and reply back via Slack Webhook API."""
    from backend.runtime.executor import execute_workflow
    
    try:
        metadata = {"channel_id": channel_id, "user_id": user_id}
        response_text = await execute_workflow(
            workflow_id=workflow_id,
            input_message=input_text,
            trigger_source="slack",
            session_id=channel_id,
            trigger_metadata=metadata,
            broadcast_callback=broadcast_callback
        )
        
        # Send reply to Slack channel
        # Requires SLACK_BOT_TOKEN
        token = os.environ.get("SLACK_BOT_TOKEN")
        if not token:
            print("[Slack] SLACK_BOT_TOKEN not found in environment. Cannot reply.")
            return
            
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            body = {
                "channel": channel_id,
                "text": response_text
            }
            res = await client.post("https://slack.com/api/chat.postMessage", headers=headers, json=body)
            print(f"[Slack] Posted reply status: {res.status_code}. Response: {res.text[:100]}")
            
    except Exception as e:
        print(f"[Slack] Error running workflow #{workflow_id}: {str(e)}")


async def handle_whatsapp_webhook(
    query_params: dict, 
    body_payload: dict,
    broadcast_callback: Optional[Callable] = None
) -> dict:
    """Process incoming WhatsApp (Meta) webhook payloads."""
    # WhatsApp Webhook Challenge verification
    # Meta sends GET request with verification hub.mode, hub.challenge, hub.verify_token
    if query_params.get("hub.mode") == "subscribe":
        verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "verify_me")
        if query_params.get("hub.verify_token") == verify_token:
            return {"challenge": int(query_params.get("hub.challenge", 0))}
        return {"status": "unauthorized"}
        
    # Process incoming message event (POST request)
    entry = body_payload.get("entry", [])
    if not entry:
        return {"status": "empty_payload"}
        
    changes = entry[0].get("changes", [])
    if not changes:
        return {"status": "empty_changes"}
        
    value = changes[0].get("value", {})
    messages = value.get("messages", [])
    if not messages:
        return {"status": "no_messages"}
        
    msg = messages[0]
    sender_phone = msg.get("from", "")  # Phone number acted as unique session_id
    msg_type = msg.get("type", "")
    
    if msg_type != "text" or not sender_phone:
        return {"status": "unsupported_format"}
        
    text = msg.get("text", {}).get("body", "")
    
    # Find active workflow with a WhatsApp Trigger
    workflow_id = None
    with Session(engine) as db:
        workflows = db.exec(select(Workflow).where(Workflow.is_active == True)).all()
        for wf in workflows:
            nodes = json.loads(wf.nodes_json)
            for node in nodes:
                if node.get("type") == "trigger" and node.get("data", {}).get("trigger_source") == "whatsapp":
                    workflow_id = wf.id
                    break
            if workflow_id:
                break
                
    if not workflow_id:
        print("[WhatsApp] No active workflow configured with a WhatsApp Trigger.")
        return {"status": "no_active_workflow"}
        
    # Run in background
    asyncio.create_task(run_whatsapp_workflow_async(
        workflow_id=workflow_id,
        input_text=text,
        phone_number=sender_phone,
        broadcast_callback=broadcast_callback
    ))
    
    return {"status": "triggered"}

async def run_whatsapp_workflow_async(
    workflow_id: int, 
    input_text: str, 
    phone_number: str,
    broadcast_callback: Optional[Callable] = None
):
    """Execute WhatsApp workflow asynchronously and reply back via Meta Graph API."""
    from backend.runtime.executor import execute_workflow
    
    try:
        metadata = {"phone_number": phone_number}
        response_text = await execute_workflow(
            workflow_id=workflow_id,
            input_message=input_text,
            trigger_source="whatsapp",
            session_id=phone_number,
            trigger_metadata=metadata,
            broadcast_callback=broadcast_callback
        )
        
        # Post back via WhatsApp Cloud API
        # Requires WHATSAPP_ACCESS_TOKEN and PHONE_NUMBER_ID
        token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
        phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
        if not token or not phone_id:
            print("[WhatsApp] WHATSAPP credentials missing. Cannot reply.")
            return
            
        url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        body = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "text",
            "text": {"body": response_text}
        }
        
        async with httpx.AsyncClient() as client:
            res = await client.post(url, headers=headers, json=body)
            print(f"[WhatsApp] Posted reply status: {res.status_code}. Response: {res.text[:100]}")
            
    except Exception as e:
        print(f"[WhatsApp] Error running workflow #{workflow_id}: {str(e)}")
