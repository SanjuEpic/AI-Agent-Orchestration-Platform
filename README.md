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

Our platform represents workflow execution as a state machine where agents, conditions, and actions form nodes, and connections form transitions. This is compiled dynamically into a LangGraph runner.

```mermaid
graph TD
    %% Clients
    U1[Visual Web UI - React Flow] <-->|REST API / WebSockets| B1[FastAPI Backend]
    U2[Telegram Bot User] <-->|Polling / Bot Events| B2[Telegram Bot Gateway]

    %% Backend Components
    subgraph FastAPI App
        B1
        B2
        S1[Background Scheduler - APScheduler] -->|Trigger Schedule| E1[LangGraph AI Orchestrator]
    end

    %% Orchestrator Components
    subgraph LangGraph AI Orchestrator
        E1 -->|Compile & Run| G1((Graph Runtime))
        G1 -->|Execute| N1[Agent Nodes]
        G1 -->|Execute| N2[Triage & Condition Nodes]
        G1 -->|Execute| N3[Action Nodes]
        N1 <-->|LLM Queries| L1[LLM Providers: Gemini, OpenAI, Anthropic]
        N1 <-->|Execute| T1[Tools Registry: Search, Calculator, Weather, Sandbox File IO]
        N3 -->|Send Message| B2
    end

    %% Persistence
    subgraph Data & Persistence
        B1 <-->|SQLModel ORM| DB[(SQLite Database: orchestrator.db)]
        E1 <-->|Save State/Logs| DB
        G1 <-->|LangGraph Checkpointer| M1[Memory Saver]
    end

    %% Styling
    classDef client fill:#818cf8,stroke:#4f46e5,stroke-width:2px,color:#fff;
    classDef backend fill:#34d399,stroke:#059669,stroke-width:2px,color:#fff;
    classDef graph fill:#fb7185,stroke:#e11d48,stroke-width:2px,color:#fff;
    classDef data fill:#fbbf24,stroke:#d97706,stroke-width:2px,color:#fff;
    
    class U1,U2 client;
    class B1,B2,S1 backend;
    class G1,N1,N2,N3 graph;
    class DB,M1 data;
```

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

### 1. Adding a New Workflow Template
* **The UI Way:**
  1. Open the visual canvas workspace under the **Design Workspace** tab.
  2. Drag your trigger, agent, action, and condition nodes onto the screen.
  3. Wire the nodes together using the connection nodes.
  4. Save the workflow, naming it. It will instantly persist as an active template.
* **The Code Way:**
  1. Open [seed.py](file:///c:/Users/aksha/OneDrive/Documents/ai-agent-orchestration/backend/db/seed.py).
  2. Define nodes and edges lists representing the React Flow schema.
  3. Create a `Workflow` database record inside `seed_database()` and run the app to apply it.

### 2. Connecting & Managing Messaging Channels

#### 🟢 Telegram (Fully Battle-Tested)
Telegram bot integrations are fully supported out-of-the-box using the built-in long-polling client.
1. **Get Bot Token**: Talk to `@BotFather` on Telegram, create a bot, and get your bot API token.
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
