import os
import json
import asyncio
from typing import List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlmodel import Session, select

# Project Imports
from backend.db.database import init_db, get_session, engine
from backend.db.seed import seed_database
from backend.db.models import Agent, Workflow, WorkflowRun, RunLog, Schedule, AgentMemory, SystemSetting, UserSessionState
from backend.runtime.channels import (
    start_telegram_bot, stop_telegram_bot, reload_telegram_bot,
    handle_slack_webhook, handle_whatsapp_webhook
)
from backend.runtime.scheduler import (
    start_scheduler, shutdown_scheduler,
    add_or_update_schedule_job, remove_schedule_job
)
from backend.runtime.executor import execute_workflow

# 1. Connection Manager for WebSocket Streaming
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WebSocket] Connected new client. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"[WebSocket] Disconnected client. Active connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send JSON payload to all active clients (UI dashboards)."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
                
        # Clean up dead sockets
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

async def websocket_broadcast_callback(event: dict):
    """Callback function used by runtime executor to stream logs and stats to UI."""
    await manager.broadcast(event)

# 2. Lifespan context manager for startup and shutdown procedures
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup:
    init_db()
    seed_database()
    
    # Load settings from database and populate environment variables
    try:
        with Session(engine) as db:
            settings_records = db.exec(select(SystemSetting)).all()
            for s in settings_records:
                if s.value:
                    os.environ[s.key] = s.value
        print("[Startup] Successfully loaded DB settings into environment variables.")
    except Exception as e:
        print(f"[Startup] Error loading settings into environment: {e}")
    
    # Start APScheduler background jobs
    await start_scheduler(broadcast_callback=websocket_broadcast_callback)
    
    # Start Telegram Long Polling Bot in background task so it doesn't block API port
    asyncio.create_task(start_telegram_bot(broadcast_callback=websocket_broadcast_callback))
    
    yield
    
    # Shutdown:
    await stop_telegram_bot()
    await shutdown_scheduler()

# Initialize FastAPI App
app = FastAPI(
    title="AI Agent Orchestration Platform",
    description="A multi-agent design workspace with real-time websocket monitoring.",
    lifespan=lifespan
)

# CORS Configuration (allows frontend dev server to connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. WebSocket Endpoint
@app.websocket("/api/ws/monitoring")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Send simple ping-pong to keep connection active
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# 4. REST API Routing Endpoints

# --- Agent CRUD ---
@app.get("/api/agents", response_model=List[Agent])
def list_agents(db: Session = Depends(get_session)):
    return db.exec(select(Agent)).all()

@app.post("/api/agents", response_model=Agent)
def create_agent(agent: Agent, db: Session = Depends(get_session)):
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent

@app.put("/api/agents/{agent_id}", response_model=Agent)
def update_agent(agent_id: int, agent_data: Agent, db: Session = Depends(get_session)):
    db_agent = db.get(Agent, agent_id)
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Exclude id and update values
    update_dict = agent_data.dict(exclude_unset=True)
    for k, v in update_dict.items():
        if k not in ("id", "created_at"):
            setattr(db_agent, k, v)
            
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_session)):
    db_agent = db.get(Agent, agent_id)
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(db_agent)
    db.commit()
    return {"message": f"Successfully deleted agent #{agent_id}"}


# --- Workflow CRUD ---
@app.get("/api/workflows", response_model=List[Workflow])
def list_workflows(db: Session = Depends(get_session)):
    return db.exec(select(Workflow)).all()

@app.get("/api/workflows/{workflow_id}", response_model=Workflow)
def get_workflow(workflow_id: int, db: Session = Depends(get_session)):
    db_wf = db.get(Workflow, workflow_id)
    if not db_wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return db_wf

@app.post("/api/workflows", response_model=Workflow)
def create_workflow(workflow: Workflow, db: Session = Depends(get_session)):
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow

@app.put("/api/workflows/{workflow_id}", response_model=Workflow)
def update_workflow(workflow_id: int, workflow_data: Workflow, db: Session = Depends(get_session)):
    db_wf = db.get(Workflow, workflow_id)
    if not db_wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
        
    update_dict = workflow_data.dict(exclude_unset=True)
    for k, v in update_dict.items():
        if k not in ("id", "created_at"):
            setattr(db_wf, k, v)
            
    db.add(db_wf)
    db.commit()
    db.refresh(db_wf)
    return db_wf

@app.delete("/api/workflows/{workflow_id}")
def delete_workflow(workflow_id: int, db: Session = Depends(get_session)):
    db_wf = db.get(Workflow, workflow_id)
    if not db_wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    db.delete(db_wf)
    db.commit()
    return {"message": f"Successfully deleted workflow #{workflow_id}"}

@app.post("/api/workflows/{workflow_id}/run")
async def trigger_workflow_manually(workflow_id: int, payload: dict, db: Session = Depends(get_session)):
    """API endpoint to trigger a workflow execution manually from the UI."""
    db_wf = db.get(Workflow, workflow_id)
    if not db_wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
        
    input_text = payload.get("message", "Triggered manual run")
    session_id = payload.get("session_id", "manual_run")
    
    # Run the execution inside a separate task so the API response resolves immediately
    # while the agent works in background, pushing results over WebSockets
    asyncio.create_task(execute_workflow(
        workflow_id=workflow_id,
        input_message=input_text,
        trigger_source="manual",
        session_id=session_id,
        trigger_metadata={"triggered_by": "Web UI"},
        broadcast_callback=websocket_broadcast_callback
    ))
    
    return {"status": "started", "workflow_id": workflow_id}


# --- Workflow Run History & Logs ---
@app.get("/api/runs")
def list_runs(db: Session = Depends(get_session)):
    # Returns last 200 runs ordered by start time to support pagination
    return db.exec(select(WorkflowRun).order_by(WorkflowRun.started_at.desc()).limit(200)).all()

@app.get("/api/runs/{run_id}")
def get_run_details(run_id: int, db: Session = Depends(get_session)):
    run = db.get(WorkflowRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    logs = db.exec(select(RunLog).where(RunLog.workflow_run_id == run_id).order_by(RunLog.timestamp.asc())).all()
    return {
        "run": run,
        "logs": logs
    }

@app.delete("/api/runs/{run_id}/cancel")
async def cancel_run(run_id: int, db: Session = Depends(get_session)):
    import datetime
    from backend.runtime.executor import active_workflow_tasks
    
    run = db.get(WorkflowRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    task = active_workflow_tasks.get(run_id)
    if task:
        task.cancel()
        print(f"[Cancellation] Requested cancellation for task of run #{run_id}")
    else:
        print(f"[Cancellation] No active task found for run #{run_id}")
        
    if run.status == "running":
        run.status = "failed"
        run.completed_at = datetime.datetime.utcnow()
        db.add(run)
        
        cancel_log = RunLog(
            workflow_run_id=run_id,
            step_type="error",
            node_id="system",
            content="Workflow run execution was cancelled by the user."
        )
        db.add(cancel_log)
        db.commit()
        
        # Broadcast real-time notifications
        await websocket_broadcast_callback({
            "type": "log",
            "step_type": "error",
            "node_id": "system",
            "workflow_run_id": run_id,
            "content": "[Cancellation] Workflow execution was cancelled."
        })
        
        await websocket_broadcast_callback({
            "type": "workflow_completed",
            "workflow_run_id": run_id,
            "status": "failed"
        })
        
    return {"status": "cancelled", "run_id": run_id}

@app.get("/api/sessions/{session_id}/stats")
def get_session_stats(session_id: str, db: Session = Depends(get_session)):
    """Aggregate token usage and cost metrics for all runs in a given session."""
    from sqlmodel import text
    query = text("""
        SELECT 
            COALESCE(SUM(l.prompt_tokens), 0) as total_prompt,
            COALESCE(SUM(l.completion_tokens), 0) as total_completion,
            COALESCE(SUM(l.thought_tokens), 0) as total_thought,
            COALESCE(SUM(l.usd_cost), 0.0) as total_cost,
            COUNT(DISTINCT w.id) as total_runs
        FROM runlog l
        JOIN workflowrun w ON l.workflow_run_id = w.id
        WHERE w.session_id = :session_id
    """)
    result = db.execute(query, {"session_id": session_id}).first()
    
    turns_count = int(result[4] or 0)
        
    return {
        "session_id": session_id,
        "total_prompt_tokens": int(result[0] or 0),
        "total_completion_tokens": int(result[1] or 0),
        "total_thought_tokens": int(result[2] or 0),
        "total_cost": round(float(result[3] or 0.0), 5),
        "total_turns": turns_count
    }


# --- Workflow-Level Memory API ---
@app.get("/api/workflows/{workflow_id}/memory")
def get_workflow_memory(workflow_id: int, db: Session = Depends(get_session)):
    memories = db.exec(select(AgentMemory).where(AgentMemory.workflow_id == workflow_id)).all()
    return memories

@app.delete("/api/workflows/{workflow_id}/memory/{key}")
def delete_workflow_memory_fact(workflow_id: int, key: str, db: Session = Depends(get_session)):
    fact = db.exec(select(AgentMemory).where(AgentMemory.workflow_id == workflow_id, AgentMemory.key == key)).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact memory key not found")
    db.delete(fact)
    db.commit()
    return {"message": f"Successfully deleted fact key '{key}'"}


# --- Schedules CRUD ---
@app.get("/api/schedules")
def list_schedules(db: Session = Depends(get_session)):
    return db.exec(select(Schedule)).all()

@app.post("/api/schedules")
async def create_schedule(sch: Schedule, db: Session = Depends(get_session)):
    db.add(sch)
    db.commit()
    db.refresh(sch)
    
    # Register/Refresh job in background scheduler
    await add_or_update_schedule_job(sch.id)
    return sch

@app.put("/api/schedules/{schedule_id}", response_model=Schedule)
async def update_schedule(schedule_id: int, sch_data: Schedule, db: Session = Depends(get_session)):
    sch = db.get(Schedule, schedule_id)
    if not sch:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    update_dict = sch_data.model_dump(exclude_unset=True)
    for k, v in update_dict.items():
        if k not in ("id", "created_at"):
            setattr(sch, k, v)
            
    db.add(sch)
    db.commit()
    db.refresh(sch)
    
    # Refresh/update job status in live background scheduler
    await add_or_update_schedule_job(sch.id)
    return sch

@app.delete("/api/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_session)):
    sch = db.get(Schedule, schedule_id)
    if not sch:
        raise HTTPException(status_code=404, detail="Schedule not found")
        
    # Remove from backend scheduler context first
    remove_schedule_job(sch.id)
    
    db.delete(sch)
    db.commit()
    return {"message": f"Deleted schedule #{schedule_id}"}


# --- Settings CRUD ---
@app.get("/api/settings")
def list_settings(db: Session = Depends(get_session)):
    settings_records = db.exec(select(SystemSetting)).all()
    return {s.key: s.value for s in settings_records}

@app.post("/api/settings")
async def save_settings(settings: dict, db: Session = Depends(get_session)):
    telegram_changed = False
    for key, val in settings.items():
        if not key:
            continue
        existing_setting = db.exec(select(SystemSetting).where(SystemSetting.key == key)).first()
        if existing_setting:
            if existing_setting.value != val:
                existing_setting.value = val
                db.add(existing_setting)
                # Dynamic update of environment variables for live runtimes
                os.environ[key] = val
                if key == "TELEGRAM_BOT_TOKEN":
                    telegram_changed = True
        else:
            new_setting = SystemSetting(key=key, value=val)
            db.add(new_setting)
            # Dynamic update of environment variables for live runtimes
            os.environ[key] = val
            if key == "TELEGRAM_BOT_TOKEN":
                telegram_changed = True
    db.commit()
    if telegram_changed:
        telegram_token = settings.get("TELEGRAM_BOT_TOKEN", "")
        asyncio.create_task(reload_telegram_bot(telegram_token))
    return {"status": "saved", "telegram_reloaded": telegram_changed}


# --- Webhooks Routing ---
@app.post("/api/webhooks/slack")
async def slack_webhook(request: Request):
    payload = await request.json()
    return await handle_slack_webhook(payload, broadcast_callback=websocket_broadcast_callback)

@app.api_route("/api/webhooks/whatsapp", methods=["GET", "POST"])
async def whatsapp_webhook(request: Request):
    # Verify GET challenge or POST payload
    query_params = dict(request.query_params)
    body = {}
    if request.method == "POST":
        body = await request.json()
        
    res = await handle_whatsapp_webhook(query_params, body, broadcast_callback=websocket_broadcast_callback)
    if "challenge" in res:
        return JSONResponse(content=res["challenge"])
    return res


# 5. Serve React Frontend Static Files
# Static assets are compiled into the frontend/dist folder.
# Mount frontend build directory in FastAPI only if compiled assets exist.
FRONTEND_DIST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

if os.path.exists(FRONTEND_DIST_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST_DIR, "assets")), name="static_assets")
    
    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        # Serve index.html for all page requests (single page application support)
        # Avoid intercepting API calls
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        return FileResponse(os.path.join(FRONTEND_DIST_DIR, "index.html"))
else:
    @app.get("/")
    def serve_api_welcome():
        return {
            "message": "AI Agent Orchestration Platform Backend API is running.",
            "notice": "Frontend build files (static files) not found. Run Vite dev server in the frontend directory."
        }
