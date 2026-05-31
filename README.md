# Yuno AI — Agent Orchestration Platform

> Submission for the Yuno AI Engineer Hiring Challenge — AI Agent Orchestration Platform.

An autonomous, self-hostable AI Agent Orchestration Platform built using **FastAPI** (Python), **LangGraph**, and **React Flow** (React/Vite).

Users can visually design agents, attach specialized tools, configure safety guardrails/interaction limits, and link them into collaborative graphs (featuring conditional branches, triage routes, and parallel execution). The platform executes workflows in real-time, streaming token metrics, USD execution costs, and agent thought trace logs directly to the browser via WebSockets.

---

## 📺 Live Demo
> [!NOTE]
> *Placeholder for the project Loom screen recording. The demo walkthrough will demonstrate:*
> 1. Editing and creating agents / workflow templates visually in the workspace.
> 2. Executing the **AI News Digest** scheduler and monitoring its logs in real-time.
> 3. Connecting to the Telegram Bot, typing `/agent`, `/reset`, and interacting live.

---

## 🏗️ System Architecture

```
                                     +----------------------+
                                     |      Web Browser     |
                                     | (React + React Flow  |
                                     |    + Tailwind CSS)   |
                                     +-----------+----------+
                                                 | REST + WebSocket
                                                 v
 +-----------------------------------------------------------------+
 |                       FastAPI Application                       |
 |                                                                 |
 |  +-------------+   +--------------+   +-----------------------+ |
 |  |   Routers   |   |  WebSocket   |   |  Telegram Bot Gateway | |
 |  |  /api/...   |   | /ws/monitor  |   |    (long polling)     | |
 |  +------+------+   +------+-------+   +-----------+-----------+ |
 |         |                 |                       |             |
 |         v                 v                       v             |
 |  +-----------------------------------------------------------+  |
 |  |  Workflow Orchestrator (backend/runtime/executor.py)      |  |
 |  |    - maps nodes/edges into LangGraph StateGraph           |  |
 |  |    - handles branching / conditions / triages             |  |
 |  |    - pipes node outputs -> next node perception memory    |  |
 |  +-------------------------+---------------------------------+  |
 |                            v                                    |
 |  +-----------------------------------------------------------+  |
 |  |  Agent Runtime (backend/runtime/executor.py & tools.py)    |  |
 |  |    - LangGraph StateGraph + LLMs (Gemini/OpenAI)          |  |
 |  |    - Multi-turn sequential tool calling loops             |  |
 |  |    - Execution cost ($/M tokens) & thought token tracking |  |
 |  |    - Context rolling windows + rolling history compaction  |  |
 |  +-------------------------+---------------------------------+  |
 |                            v                                    |
 |  +-----------------------------------------------------------+  |
 |  |  Persistence (SQLModel + SQLite: orchestrator.db)          |  |
 |  |  tables: agents, workflows, runs, logs, schedules, msgs   |  |
 |  +-----------------------------------------------------------+  |
 +-----------------------------------------------------------------+
                                      ^
                                      | HTTPS
                              +-------+--------+
                              |    Telegram    |
                              |  (user chat)   |
                              +----------------+
```

---

## 🛠️ Tech Stack & Justifications

| Decision | Choice | Why |
| :--- | :--- | :--- |
| **Language (Backend)** | **Python 3.10+** | Rich AI/LLM ecosystem. Native compatibility with LangGraph, SQLModel, and asynchronous packages like `python-telegram-bot`. |
| **Agent Framework** | **LangGraph** | Enables stateful multi-agent workflows, loops, and conditional branching as a native directed acyclic graph (DAG), which aligns perfectly with the hiring challenge's visual builder specs. |
| **LLM Providers** | **Gemini, OpenAI** | Support for premium model suites. Configurable dynamically per-agent in the workspace so users can utilize the best model for each task (e.g. Gemini for search tools, GPT-4o for complex triage). |
| **Web Framework** | **FastAPI** | Async-first performance, perfect for streaming token logs/cost tracking via WebSockets and handling background scheduler operations simultaneously. |
| **Persistence** | **SQLModel + SQLite** | Local file-based SQLite database (`orchestrator.db`) ensures zero-config local runs. Enabling Write-Ahead Logging (WAL) handles high concurrent read/write transactions smoothly. |
| **Frontend** | **React (Vite) + React Flow** | React Flow provides a premium, responsive drag-and-drop workspace for designing agent graph topologies. Compiled static assets are served directly from the FastAPI backend. |
| **Messaging Channel** | **Telegram (python-telegram-bot)** | Fully integrated messaging bot. Provides instant multi-turn agent chats without business verifications (WhatsApp) or workspace setups (Slack). |

---

## 🗂️ Clean Separation of Layers

| Layer | Responsibility | Files & Directories |
| :--- | :--- | :--- |
| **UI Workspace** | Modern React (Vite) interface, utilizing React Flow for node-link diagrams, custom glassmorphism style rules, WebSocket telemetry listeners. | [frontend/src/App.jsx](file:///c:/Users/aksha/OneDrive/Documents/ai-agent-orchestration/frontend/src/App.jsx), [frontend/src/index.css](file:///c:/Users/aksha/OneDrive/Documents/ai-agent-orchestration/frontend/src/index.css) |
| **API Routers** | FastAPI endpoints handling REST CRUD operations for agents, workflows, schedules, and WebSocket monitoring streams. | [backend/main.py](file:///c:/Users/aksha/OneDrive/Documents/ai-agent-orchestration/backend/main.py) |
| **Orchestrator** | Dynamic LangGraph compiler that maps visual node connections into a StateGraph, managing state, reducers, and flow transitions. | [backend/runtime/executor.py](file:///c:/Users/aksha/OneDrive/Documents/ai-agent-orchestration/backend/runtime/executor.py) |
| **Agent Runtime** | LLM factory client instantiation (Gemini, OpenAI, Anthropic), conversational agent logic, rolling window memory compaction, and citation formatting. | [backend/runtime/executor.py](file:///c:/Users/aksha/OneDrive/Documents/ai-agent-orchestration/backend/runtime/executor.py) |
| **Tools Registry** | Integrations for external agent actions (DuckDuckGo Search/Scrape, AST-safe Calculator, Weather Geocoding, Sandboxed File Workspace). | [backend/runtime/tools.py](file:///c:/Users/aksha/OneDrive/Documents/ai-agent-orchestration/backend/runtime/tools.py) |
| **Messaging Gateway** | Multi-channel messaging handlers, featuring a long-polling Telegram bot worker and webhook endpoints for Slack and WhatsApp. | [backend/runtime/channels.py](file:///c:/Users/aksha/OneDrive/Documents/ai-agent-orchestration/backend/runtime/channels.py) |
| **Data Layer** | SQLite database connection setups, database model definitions, and automatic seeding scripts. | [backend/db/models.py](file:///c:/Users/aksha/OneDrive/Documents/ai-agent-orchestration/backend/db/models.py), [backend/db/seed.py](file:///c:/Users/aksha/OneDrive/Documents/ai-agent-orchestration/backend/db/seed.py) |

---

## 🚀 Quick Start (Single-Command Local Run)

### Prerequisites
* Python 3.10+ installed
* Node.js (with `npm`) installed

### Setup & Run
1. Clone this repository and open the project workspace.
2. Create a `.env` file in the root directory and add your API credentials:
   ```env
   # LLM Keys
   GEMINI_API_KEY=your_gemini_api_key
   OPENAI_API_KEY=your_openai_api_key
   
   # Telegram Bot (Primary messaging channel)
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   ```
   *(Alternatively, if you prefer a UI-first setup, you can leave these blank in the `.env` file and configure them directly under the **Settings** tab in the Web UI after booting).*

   ![UI Settings Configuration](docs/frontend_plots/settings-config.png)

3. Run the bootloader script from the project root:
   ```bash
   python run.py
   ```
   *This script automatically checks and installs Python libraries, resolves npm modules, compiles frontend static assets, migrates/seeds the database, and boots the FastAPI server.*
4. Open the Web UI in your browser at: **`http://localhost:8000`**

*(For active hot-reloading development where frontend changes refresh automatically, run `python run.py --dev` to launch Vite on `3000` and Uvicorn on `8000` concurrently).*

---

## 🧪 Running the Test Suite
The critical paths (Agent configurations, graph parsing, price calculators, session histories, memory templates, and webhook triages) are guarded by **27 unit tests**. Run them locally with:
```bash
pytest backend/tests
```

---

## 🏗️ Adding Templates or Channels

### 📋 Predefined Seeded Workflows

The platform database is automatically pre-seeded with three battle-tested multi-agent template graphs on startup (configured in [seed.py](file:///c:/Users/aksha/OneDrive/Documents/ai-agent-orchestration/backend/db/seed.py)):

1. **Smart Support Escalation Router**
   * **Purpose**: Demonstrates semantic triage, conditional branching, and escalation logic.
   * **Flow**: Telegram Trigger ➡️ Triage Classifier (checks if query is support-related) ➡️ (If support) Technical Support Agent ➡️ Condition Gate (checks if issue requires Tier-2 escalation) ➡️ Telegram Reply (Escalated notice or direct resolution). Non-support queries are sent to a general log archive action.
2. **AI News Digest**
   * **Purpose**: Demonstrates sequential multi-agent orchestration, web search tools, and scheduling.
   * **Flow**: Telegram Trigger / APScheduler Trigger ➡️ AI News Collector Agent (gathers tech news using search tool) ➡️ AI News Summarizer Agent (compiles bulleted markdown digest) ➡️ Post to Telegram Action.
3. **Parallel Travel Planner**
   * **Purpose**: Demonstrates asynchronous, parallel multi-agent collaboration and consolidation.
   * **Flow**: Telegram Trigger ➡️ Splits concurrently into two parallel execution branches:
     * Branch A: Weather Expert Agent (queries weather tool)
     * Branch B: Local Tour Guide Agent (queries search tool for local sights)
     * ➡️ Consolidates into Travel Coordinator Agent (compiles weather + attractions into a unified 3-day itinerary) ➡️ Send Telegram Reply Action.

---

### 1. Adding a New Workflow Template

The platform supports adding new workflow designs either visually through the browser workspace or programmatically in the codebase.

#### 🎨 The UI Way (Visual Canvas)
1. **Navigate**: Go to the **Design Workspace** tab in the Web UI.
2. **Assemble**: Drag nodes onto the canvas (Triggers, Agents, Actions, and Conditions).
3. **Connect**: Link node handles together to define flow progression and conditional branching paths.
4. **Persist**: Click **Save Workflow**, name your design, and it will immediately become available to run or schedule.

#### 💻 The Code Way (Database Seeding)
1. **Open Seeder**: Open [seed.py](file:///c:/Users/aksha/OneDrive/Documents/ai-agent-orchestration/backend/db/seed.py).
2. **Define Nodes & Edges**: Set up lists representing the React Flow JSON graph structures:
   ```python
   nodes = [
       {"id": "trigger_1", "type": "trigger", "data": {"type": "telegram"}},
       {"id": "agent_1", "type": "agent", "data": {"agent_id": 1}}
   ]
   edges = [
       {"id": "e1-edge", "source": "trigger_1", "target": "agent_1"}
   ]
   ```
3. **Save Record**: Insert and commit a new `Workflow` object in the database inside the `seed_database()` function:
   ```python
   custom_workflow = Workflow(
       name="My Programmatic Flow",
       description="Seeded agent workflow template",
       nodes=nodes,
       edges=edges
   )
   db.add(custom_workflow)
   ```
4. **Boot**: Run `python run.py` to auto-execute the database seeder and register the workflow in the backend database.


### 2. Connecting & Managing Messaging Channels

#### 🟢 Telegram (Fully Battle-Tested)
Telegram bot integrations are fully supported out-of-the-box using the built-in long-polling client.
1. **Get Bot Token from `@BotFather`**:
   * Open the Telegram app, search for the official **`@BotFather`** account, and start a chat.
   * Send the `/newbot` command.
   * Choose a friendly name for your bot (e.g., `My Orchestration Agent`).
   * Choose a unique username ending in `bot` (e.g., `my_agent_platform_bot`).
   * `@BotFather` will reply with your API token (e.g., `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`). Copy this token.
2. **Configure Settings**: Go to the **Settings** tab in the UI, input your token under **Telegram Bot Token**, and click save. The backend dynamically reloads and boots the polling worker.
3. **Connect to bot**: Open your bot on Telegram, send **/start** to retrieve your unique **Chat ID**.
4. **Link schedules**: Paste this Chat ID into any schedule registration form in the UI. When scheduled cron tasks run in the background (e.g. news digests), they will directly message you.

#### 🟡 Slack & WhatsApp (Optional / Infrastructure Code Ready)
Webhooks for Slack and WhatsApp Meta Graph APIs are implemented in [channels.py](file:///c:/Users/aksha/OneDrive/Documents/ai-agent-orchestration/backend/runtime/channels.py).
1. Configure a public tunnel to direct incoming requests to your local instance:
   ```bash
   ngrok http 8000
   ```
2. **Slack Webhook Hook:** Set the **Event Subscriptions Request URL** in the Slack App Portal to `https://<ngrok-url>/api/webhooks/slack` and subscribe to `app_mention` messages.
3. **WhatsApp Webhook Hook:** Set the **Meta Webhook Callback URL** to `https://<ngrok-url>/api/webhooks/whatsapp` and configure your verification token.

---

## 🔌 API Endpoints Reference

The backend exposes a clean REST and WebSocket API. The interactive OpenAPI documentation is auto-generated and accessible locally at **`http://localhost:8000/docs`**.

### 🎙️ Live Telemetry
* **`WS /api/ws/monitoring`**: Persistent WebSocket connection to broadcast live execution logs, token usage, cost calculations, and active nodes to visual dashboard clients.

### 🤖 Agents (CRUD)
* **`GET /api/agents`**: Retrieves all configured agents.
* **`POST /api/agents`**: Registers a new agent configuration.
* **`PUT /api/agents/{agent_id}`**: Updates parameters (tools, personality, model, memory limits) for a specific agent.
* **`DELETE /api/agents/{agent_id}`**: Deletes an agent record.

### 🏗️ Workflows & Execution
* **`GET /api/workflows`**: Lists all visual graph templates.
* **`GET /api/workflows/{workflow_id}`**: Returns node and edge connections for a workflow.
* **`POST /api/workflows`**: Registers a new visual workflow graph.
* **`PUT /api/workflows/{workflow_id}`**: Updates a workflow's topology.
* **`DELETE /api/workflows/{workflow_id}`**: Deletes a workflow.
* **`POST /api/workflows/{workflow_id}/run`**: Triggers a manual execution of a workflow run in the background.

### 📊 Run Logs & Memory
* **`GET /api/runs`**: Returns history records for all runs.
* **`GET /api/runs/{run_id}`**: Returns detailed logs and results for a specific execution run.
* **`DELETE /api/runs/{run_id}/cancel`**: Requests cancellation of an active workflow run task.
* **`GET /api/sessions/{session_id}/stats`**: Aggregates token usage, run counts, and execution costs for a given session.
* **`GET /api/workflows/{workflow_id}/memory`**: Lists long-term memories and facts extracted for a workflow.
* **`DELETE /api/workflows/{workflow_id}/memory/{key}`**: Deletes a long-term key-value memory fact.

### 📅 Background Schedules
* **`GET /api/schedules`**: Lists all automated schedules.
* **`POST /api/schedules`**: Creates and activates a new background cron job.
* **`PUT /api/schedules/{schedule_id}`**: Modifies a cron configuration.
* **`DELETE /api/schedules/{schedule_id}`**: De-activates and deletes a scheduled job.

### ⚙️ System Settings & Webhooks
* **`GET /api/settings`**: Retrieves key configurations (keys, tokens) from database records.
* **`POST /api/settings`**: Saves configurations (auto-starts/reloads Telegram bot upon token update).
* **`POST /api/webhooks/slack`**: Webhook gateway receiver for Slack integrations.
* **`GET/POST /api/webhooks/whatsapp`**: Webhook gateway receiver for Meta WhatsApp integrations.

---

## ⚠️ Known Limitations & Production Considerations

1. **Telegram Client-Initiation Restraint**: Bots cannot proactively message a user on Telegram unless the user has first typed `/start` or interacted with the bot. Scheduled cron triggers will fail to deliver messages if the user has not initialized the bot.
2. **In-Process Scheduler (APScheduler)**: The background scheduler runs directly within the main FastAPI application process. If the server is stopped or restarted, scheduled tasks do not execute. There is no external task broker (like Redis/Celery) to coordinate/retry schedules across multiple server instances.
3. **No LLM Request Throttling / Queuing**: External LLM client calls are made immediately. In workflows with intensive parallel nodes or tight tool loops, the platform doesn't queue requests or apply automatic exponential backoffs, making it susceptible to API rate limits (`HTTP 429`).

