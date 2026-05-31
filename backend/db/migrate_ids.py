import json
import sqlite3
from sqlmodel import Session, select
from backend.db.database import engine
from backend.db.models import Workflow, Schedule, WorkflowRun, AgentMemory, UserSessionState

def run_migration():
    print("[Migration] Starting database update...")
    
    # 1. Update Workflow 1 (Slack -> Telegram elements and description)
    with Session(engine) as session:
        w1 = session.get(Workflow, 1)
        if w1:
            w1.description = "Incoming Telegram messages are classified. High-value enterprise prospects receive a tailored pitch, while spam messages are logged and archived."
            
            # Update nodes json
            nodes = json.loads(w1.nodes_json)
            for node in nodes:
                if node.get("id") == "node_trigger":
                    node["data"]["label"] = "Telegram Message Trigger"
                    node["data"]["trigger_source"] = "telegram"
                elif node.get("id") == "node_action_reply":
                    node["data"]["label"] = "Send Pitch via Telegram"
                    node["data"]["action_type"] = "telegram_reply"
                elif node.get("id") == "node_action_archive":
                    node["data"]["archive_message"] = "Thank you, your message has been logged/archived."
            w1.nodes_json = json.dumps(nodes)
            session.add(w1)
            session.commit()
            print("[Migration] Updated Workflow 1 nodes and description to use Telegram.")
            
    # 2. Update IDs (3 -> 2, 4 -> 3) using raw SQLite because primary key updates can be tricky in SQLAlchemy/SQLModel
    conn = sqlite3.connect("orchestrator.db")
    cursor = conn.cursor()
    
    try:
        # Turn off foreign keys temporarily to do updates
        cursor.execute("PRAGMA foreign_keys = OFF;")
        
        # Check if ID 2 already exists
        cursor.execute("SELECT id FROM workflow WHERE id = 2;")
        if cursor.fetchone():
            print("[Migration] Workflow ID 2 already exists! Shifting might have already been partially applied.")
            # We can still proceed if ID 3 or 4 exists
            
        # Shifting Workflow 3 -> 2
        cursor.execute("SELECT id FROM workflow WHERE id = 3;")
        if cursor.fetchone():
            print("[Migration] Shifting Workflow 3 -> 2...")
            cursor.execute("UPDATE workflow SET id = 2 WHERE id = 3;")
            cursor.execute("UPDATE workflowrun SET workflow_id = 2 WHERE workflow_id = 3;")
            cursor.execute("UPDATE agentmemory SET workflow_id = 2 WHERE workflow_id = 3;")
            cursor.execute("UPDATE usersessionstate SET active_workflow_id = 2 WHERE active_workflow_id = 3;")
        
        # Shifting Workflow 4 -> 3
        cursor.execute("SELECT id FROM workflow WHERE id = 4;")
        if cursor.fetchone():
            print("[Migration] Shifting Workflow 4 -> 3...")
            cursor.execute("UPDATE workflow SET id = 3 WHERE id = 4;")
            cursor.execute("UPDATE schedule SET workflow_id = 3 WHERE workflow_id = 4;")
            cursor.execute("UPDATE workflowrun SET workflow_id = 3 WHERE workflow_id = 4;")
            cursor.execute("UPDATE agentmemory SET workflow_id = 3 WHERE workflow_id = 4;")
            cursor.execute("UPDATE usersessionstate SET active_workflow_id = 3 WHERE active_workflow_id = 4;")
        
        # Reset the autoincrement counter for workflow table to 3 (if sequence table exists)
        try:
            cursor.execute("UPDATE sqlite_sequence SET seq = 3 WHERE name = 'workflow';")
        except sqlite3.OperationalError:
            print("[Migration] sqlite_sequence table does not exist, skipping counter reset.")
        
        conn.commit()
        print("[Migration] Successfully completed ID shifting step.")
        
    except Exception as e:
        conn.rollback()
        print(f"[Migration ERROR] Failed to shift IDs: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
