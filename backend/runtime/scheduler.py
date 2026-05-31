import json
from typing import Optional, Callable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select
from backend.db.database import engine
from backend.db.models import Schedule, Workflow

# Active scheduler instance
scheduler: Optional[AsyncIOScheduler] = None
global_broadcast_callback: Optional[Callable] = None

def get_job_id(schedule_id: int) -> str:
    return f"workflow_schedule_{schedule_id}"

async def trigger_scheduled_workflow(workflow_id: int, schedule_id: int):
    """Callback function triggered by APScheduler to run a workflow on interval."""
    # Import executor locally to avoid circular dependencies
    from backend.runtime.executor import execute_workflow
    
    print(f"[Scheduler] Automatically triggering workflow #{workflow_id} (Schedule #{schedule_id})")
    
    # Check if workflow is active
    with Session(engine) as db:
        workflow = db.get(Workflow, workflow_id)
        if not workflow or not workflow.is_active:
            print(f"[Scheduler] Workflow #{workflow_id} is inactive or missing. Skipping run.")
            return
            
        schedule = db.get(Schedule, schedule_id)
        if not schedule or not schedule.is_active:
            print(f"[Scheduler] Schedule #{schedule_id} is inactive or missing. Skipping run.")
            return

    # Use default prompt message for schedules
    input_message = f"Execute scheduled workflow '{workflow.name}'"
    session_id = f"schedule_{workflow_id}"
    chat_id = schedule.chat_id
    metadata = {"schedule_id": schedule_id, "cron": schedule.cron_expression, "chat_id": chat_id}

    try:
        final_output = await execute_workflow(
            workflow_id=workflow_id,
            input_message=input_message,
            trigger_source="schedule",
            session_id=session_id,
            trigger_metadata=metadata,
            broadcast_callback=global_broadcast_callback
        )
        print(f"[Scheduler] Successfully finished scheduled execution for workflow #{workflow_id}")

        # Deliver the output to Telegram if a destination chat is configured.
        # Scheduled runs have no inbound message to reply to, so we send proactively.
        if chat_id and final_output:
            from backend.runtime.channels import send_telegram_message
            sent = await send_telegram_message(str(chat_id), final_output)
            if sent:
                print(f"[Scheduler] Delivered scheduled output for workflow #{workflow_id} to chat {chat_id}")
        elif not chat_id:
            print(f"[Scheduler] No chat_id set for Schedule #{schedule_id}; output not delivered to Telegram.")
    except Exception as e:
        print(f"[Scheduler] Error running scheduled workflow #{workflow_id}: {str(e)}")

async def start_scheduler(broadcast_callback: Optional[Callable] = None):
    """Load active schedules from the database and boot the background job scheduler."""
    global scheduler, global_broadcast_callback
    global_broadcast_callback = broadcast_callback
    
    if scheduler:
        print("[Scheduler] Scheduler already running. Skipping initialization.")
        return
        
    scheduler = AsyncIOScheduler()
    
    # Retrieve active schedules from database
    with Session(engine) as db:
        active_schedules = db.exec(select(Schedule).where(Schedule.is_active == True)).all()
        
    print(f"[Scheduler] Initializing Scheduler with {len(active_schedules)} active schedules.")
    
    for sch in active_schedules:
        try:
            job_id = get_job_id(sch.id)
            trigger = CronTrigger.from_crontab(sch.cron_expression)
            scheduler.add_job(
                trigger_scheduled_workflow,
                trigger=trigger,
                args=[sch.workflow_id, sch.id],
                id=job_id,
                replace_existing=True
            )
            print(f"[Scheduler] Registered Schedule #{sch.id} (Cron: '{sch.cron_expression}') for Workflow #{sch.workflow_id}")
        except Exception as e:
            print(f"[Scheduler] Failed to register Schedule #{sch.id}: {str(e)}")
            
    scheduler.start()
    print("[Scheduler] Background scheduler loop successfully started.")

async def shutdown_scheduler():
    """Safely shut down the background scheduler loop."""
    global scheduler
    if scheduler:
        scheduler.shutdown()
        scheduler = None
        print("Scheduler successfully stopped.")

async def add_or_update_schedule_job(schedule_id: int):
    """Add a new job or refresh an existing job in the active scheduler scheduler context."""
    global scheduler
    if not scheduler:
        return
        
    with Session(engine) as db:
        sch = db.get(Schedule, schedule_id)
        if not sch:
            # If deleted, remove the job
            remove_schedule_job(schedule_id)
            return
            
        if not sch.is_active:
            # If deactivated, remove the job
            remove_schedule_job(schedule_id)
            return
            
        try:
            job_id = get_job_id(sch.id)
            trigger = CronTrigger.from_crontab(sch.cron_expression)
            scheduler.add_job(
                trigger_scheduled_workflow,
                trigger=trigger,
                args=[sch.workflow_id, sch.id],
                id=job_id,
                replace_existing=True
            )
            print(f"[Scheduler] Updated Schedule #{sch.id} (Cron: '{sch.cron_expression}') for Workflow #{sch.workflow_id}")
        except Exception as e:
            print(f"[Scheduler] Failed to update Schedule #{sch.id}: {str(e)}")

def remove_schedule_job(schedule_id: int):
    """Unregister a job from the active scheduler context."""
    global scheduler
    if not scheduler:
        return
        
    job_id = get_job_id(schedule_id)
    try:
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            print(f"[Scheduler] Unregistered job ID: {job_id}")
    except Exception as e:
        print(f"[Scheduler] Error removing job ID {job_id}: {str(e)}")
