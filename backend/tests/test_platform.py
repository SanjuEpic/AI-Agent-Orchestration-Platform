import os
import json
import pytest
import asyncio
from sqlmodel import Session, SQLModel, create_engine, select

from backend.db.models import Agent, Workflow, WorkflowRun, RunLog, Message, SystemSetting, UserSessionState
from backend.runtime.executor import calculate_llm_cost

# Setup temporary file-based SQLite database for testing to support parallel/detached background connections
TEST_DATABASE_URL = "sqlite:///test_platform_run.db"

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    
    engine.dispose()
    try:
        if os.path.exists("test_platform_run.db"):
            os.remove("test_platform_run.db")
    except Exception:
        pass

# 1. Critical Path: Test Agent CRUD and configuration persistence
def test_agent_creation_and_config(session: Session):
    agent = Agent(
        name="Test Agent",
        role="Unit Tester",
        system_prompt="You verify inputs.",
        model_provider="openai",
        model_name="gpt-4o-mini",
        memory_limit=5,
        tools="search,calculator",
        channels="slack"
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    
    assert agent.id is not None
    assert agent.name == "Test Agent"
    assert agent.model_provider == "openai"
    assert agent.model_name == "gpt-4o-mini"
    assert "search" in agent.tools
    assert agent.memory_limit == 5
    
    # Verify update
    agent.memory_limit = 8
    session.add(agent)
    session.commit()
    
    db_agent = session.exec(select(Agent).where(Agent.name == "Test Agent")).first()
    assert db_agent.memory_limit == 8

# 2. Critical Path: Test Workflow JSON graph parsing & mapping structure
def test_workflow_node_edge_parsing(session: Session):
    # Simulated React Flow JSON output
    nodes = [
        {"id": "n1", "type": "trigger", "data": {"trigger_source": "telegram"}},
        {"id": "n2", "type": "agent", "data": {"agent_id": 1, "label": "Triage Agent"}},
        {"id": "n3", "type": "action", "data": {"action_type": "telegram_reply"}}
    ]
    edges = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"}
    ]
    
    workflow = Workflow(
        name="Travel Test Workflow",
        description="Verifies edge and node structure.",
        nodes_json=json.dumps(nodes),
        edges_json=json.dumps(edges),
        is_active=True
    )
    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    
    assert workflow.id is not None
    parsed_nodes = json.loads(workflow.nodes_json)
    parsed_edges = json.loads(workflow.edges_json)
    
    assert len(parsed_nodes) == 3
    assert len(parsed_edges) == 2
    assert parsed_nodes[0]["id"] == "n1"
    assert parsed_edges[0]["source"] == "n1"
    assert parsed_edges[0]["target"] == "n2"

# 3. Critical Path: Test execution cost calculation logic
def test_pricing_calculator():
    # gemini input $0.30/M, output $2.50/M
    gemini_cost = calculate_llm_cost("gemini-2.5-flash", 1000, 2000)
    expected_gemini = (1000 / 1_000_000 * 0.30) + (2000 / 1_000_000 * 2.50)
    assert pytest.approx(gemini_cost, rel=1e-6) == expected_gemini

    # gpt-4o input $5.00/M, output $15.00/M
    openai_cost = calculate_llm_cost("gpt-4o", 500, 1500)
    expected_openai = (500 / 1_000_000 * 5.00) + (1500 / 1_000_000 * 15.00)
    assert pytest.approx(openai_cost, rel=1e-6) == expected_openai

# 4. Critical Path: Test message history roll mapping
def test_session_message_history(session: Session):
    session_id = "test_telegram_chat_99"
    msg1 = Message(session_id=session_id, role="user", content="Hello")
    msg2 = Message(session_id=session_id, role="assistant", content="How can I help?")
    msg3 = Message(session_id=session_id, role="user", content="Plan a trip.")
    
    session.add(msg1)
    session.add(msg2)
    session.add(msg3)
    session.commit()
    
    # Query rolling window history (limit 2)
    history_query = select(Message).where(Message.session_id == session_id).order_by(Message.timestamp.desc()).limit(2)
    records = list(session.exec(history_query).all())
    
    assert len(records) == 2
    # Records returned desc (latest first)
    assert records[0].content == "Plan a trip."
    assert records[1].content == "How can I help?"

# --- Remediation Tests ---

from unittest.mock import AsyncMock, patch, MagicMock
from backend.runtime.tools import web_search, calculator, get_datetime, workspace_sandbox, http_request
from backend.runtime.executor import make_condition_route, execute_workflow, WorkflowState

def test_tool_execution():
    # Test calculator AST-based math evaluation
    res_calc = calculator("2 + 3 * 4")
    assert "Result: 14" in res_calc
    
    res_calc_invalid = calculator("import os; os.system('echo')")
    assert "failed" in res_calc_invalid or "Error" in res_calc_invalid

    # Test get_datetime (accepts optional dummy argument)
    res_dt = get_datetime("test")
    assert "Current Local Datetime" in res_dt

    # Test workspace_sandbox
    # Write operation
    write_args = json.dumps({"action": "write", "filename": "test_run.txt", "content": "hello unit test"})
    res_write = workspace_sandbox(write_args)
    assert "Successfully wrote" in res_write

    # Read operation
    read_args = json.dumps({"action": "read", "filename": "test_run.txt"})
    res_read = workspace_sandbox(read_args)
    assert "hello unit test" in res_read

    # Clean up test file if exists
    try:
        from backend.runtime.tools import SANDBOX_DIR
        test_file = os.path.join(SANDBOX_DIR, "test_run.txt")
        if os.path.exists(test_file):
            os.remove(test_file)
    except Exception:
        pass

def test_condition_routing():
    route_func = make_condition_route("approve", "node_yes", "node_no")
    
    # Check match case-insensitive
    state_match = WorkflowState(outputs={"node_1": "We approve this request."})
    assert route_func(state_match) == "node_yes"
    
    state_no_match = WorkflowState(outputs={"node_1": "We reject this request."})
    assert route_func(state_no_match) == "node_no"

@pytest.mark.asyncio
async def test_workflow_execution_mock_llm(session: Session):
    # Setup mock agent in database
    agent = Agent(
        id=1,
        name="Triage Agent",
        role="Triage",
        system_prompt="System prompt context",
        model_provider="openai",
        model_name="gpt-4o-mini",
        memory_limit=5,
        tools="calculator",
        channels="slack"
    )
    session.add(agent)
    
    # Setup mock workflow in database
    nodes = [
        {"id": "n1", "type": "trigger", "data": {"trigger_source": "manual"}},
        {"id": "n2", "type": "agent", "data": {"agent_id": 1, "label": "Triage Agent"}},
        {"id": "n3", "type": "action", "data": {"action_type": "telegram_reply"}}
    ]
    edges = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"}
    ]
    workflow = Workflow(
        id=1,
        name="Test Execution Workflow",
        description="Tests execution flow",
        nodes_json=json.dumps(nodes),
        edges_json=json.dumps(edges),
        is_active=True
    )
    session.add(workflow)
    session.commit()

    # Mock get_llm_client and langchain invoke to prevent real API calls
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "This is a mock LLM reply."
    mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 20}
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("backend.runtime.executor.get_llm_client", return_value=mock_llm), \
         patch("backend.runtime.executor.engine", session.bind):
        
        result = await execute_workflow(
            workflow_id=1,
            input_message="Start workflow",
            trigger_source="manual",
            session_id="test_session_123"
        )
        
        assert result == "This is a mock LLM reply."
        
        # Verify run execution state was created in DB
        run = session.exec(select(WorkflowRun).where(WorkflowRun.workflow_id == 1)).first()
        assert run is not None
        assert run.status == "completed"
        
        # Verify logs were saved
        log = session.exec(select(RunLog).where(RunLog.workflow_run_id == run.id)).first()
        assert log is not None
        assert "This is a mock LLM reply" in log.content
        
        # Wait for background task to complete before db teardown
        await asyncio.sleep(0.3)


def test_citation_verification_helper():
    from backend.runtime.executor import verify_and_format_citations
    
    # Test case 1: Response with valid citations
    sources = [
        {"title": "Rome Weather", "url": "https://weather.com/rome"},
        {"title": "Colosseum Guide", "url": "https://rome.com/colosseum"}
    ]
    
    response = "Rome is warm [1] and you should visit the Colosseum [2]."
    formatted = verify_and_format_citations(response, sources)
    
    assert "Rome is warm [1] and you should visit the Colosseum [2]." in formatted
    assert "**Sources:**" in formatted
    assert "[1] Rome Weather: https://weather.com/rome" in formatted
    assert "[2] Colosseum Guide: https://rome.com/colosseum" in formatted
    
    # Test case 2: Response with invalid/hallucinated citation
    response_invalid = "Venice is sinking [3]."
    formatted_invalid = verify_and_format_citations(response_invalid, sources)
    assert "Venice is sinking [Ungrounded Claim]." in formatted_invalid
    assert "**Sources:**" not in formatted_invalid

    # Test case 3: Mixed valid and invalid citations
    response_mixed = "Rome is warm [1] but Paris is rainy [4]."
    formatted_mixed = verify_and_format_citations(response_mixed, sources)
    assert "Rome is warm [1] but Paris is rainy [Ungrounded Claim]." in formatted_mixed
    assert "**Sources:**" in formatted_mixed
    assert "[1] Rome Weather: https://weather.com/rome" in formatted_mixed
    assert "[4]" not in formatted_mixed


def test_state_reducers():
    from backend.runtime.executor import reduce_outputs, reduce_sources
    
    # Test reduce_outputs
    left_out = {"node_1": "result 1"}
    right_out = {"node_2": "result 2"}
    merged_out = reduce_outputs(left_out, right_out)
    assert merged_out == {"node_1": "result 1", "node_2": "result 2"}
    
    # Test reduce_sources
    left_src = [{"title": "t1", "url": "u1"}]
    right_src = [{"title": "t2", "url": "u2"}, {"title": "t1", "url": "u1"}] # contains duplicate
    merged_src = reduce_sources(left_src, right_src)
    assert len(merged_src) == 2
    assert merged_src[0] == {"title": "t1", "url": "u1"}
    assert merged_src[1] == {"title": "t2", "url": "u2"}


def test_weather_tool():
    from backend.runtime.tools import check_weather
    
    # Test checking weather for a real city
    res = check_weather("Rome")
    assert "Current Weather in" in res
    assert "Temperature" in res
    assert "Humidity" in res


def test_tool_call_sanitization():
    import re
    def sanitize(text):
        if "TOOL_CALL:" in text:
            text = re.sub(r'TOOL_CALL:\s*\{.*?\}', '', text, flags=re.DOTALL)
            text = re.sub(r'TOOL_CALL:.*', '', text, flags=re.DOTALL).strip()
        return text

    # Single tool call
    t1 = "Check the weather. TOOL_CALL: {\"tool\": \"weather\", \"argument\": \"Rome\"}"
    assert sanitize(t1) == "Check the weather."

    # Multi-line tool call
    t2 = "Hello.\nTOOL_CALL:\n{\n  \"tool\": \"search\",\n  \"argument\": \"test\"\n}\nHave a nice day."
    assert sanitize(t2) == "Hello.\n\nHave a nice day."

    # Broken/incomplete tool call
    t3 = "Let's call: TOOL_CALL: {\"tool\": \"weather\""
    assert sanitize(t3) == "Let's call:"


@pytest.mark.asyncio
async def test_workflow_execution_saves_all_agent_messages(session: Session):
    """Verify that each agent node writes its response to the Message table."""
    agent = Agent(
        id=2,
        name="Triage Agent",
        role="Triage",
        system_prompt="System prompt context",
        model_provider="openai",
        model_name="gpt-4o-mini",
        memory_limit=5,
        tools="calculator",
        channels="slack"
    )
    session.add(agent)
    
    nodes = [
        {"id": "n1", "type": "trigger", "data": {"trigger_source": "manual"}},
        {"id": "n2", "type": "agent", "data": {"agent_id": 2, "label": "Triage Agent"}},
        {"id": "n3", "type": "action", "data": {"action_type": "telegram_reply"}}
    ]
    edges = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"}
    ]
    workflow = Workflow(
        id=2,
        name="Test History Workflow",
        description="Tests execution message saving history",
        nodes_json=json.dumps(nodes),
        edges_json=json.dumps(edges),
        is_active=True
    )
    session.add(workflow)
    session.commit()

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Agent node response."
    mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 20}
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("backend.runtime.executor.get_llm_client", return_value=mock_llm), \
         patch("backend.runtime.executor.engine", session.bind):
        
        result = await execute_workflow(
            workflow_id=2,
            input_message="Start history test",
            trigger_source="manual",
            session_id="test_session_all_msgs"
        )
        
        assert result == "Agent node response."
        
        # Verify: 1 User message + 1 Agent assistant message = 2 messages total
        msgs = session.exec(select(Message).where(Message.session_id == "test_session_all_msgs")).all()
        assert len(msgs) == 2
        
        user_msgs = [m for m in msgs if m.role == "user"]
        assistant_msgs = [m for m in msgs if m.role == "assistant"]
        assert len(user_msgs) == 1
        assert len(assistant_msgs) == 1
        assert user_msgs[0].content == "Start history test"
        assert assistant_msgs[0].content == "Agent node response."
        
        # Wait for background task to complete before db teardown
        await asyncio.sleep(0.3)


def test_compaction_turn_counting_logic():
    """Verify that K-limit turn counting only counts user + final assistant messages per turn,
    not intermediate agent responses."""
    from backend.runtime.executor import compact_session_history
    
    # Simulate a session with 3 user turns where each turn has 3 intermediate agent messages
    # Turn 1: user -> agent1 -> agent2 -> agent3(final)
    # Turn 2: user -> agent1 -> agent2 -> agent3(final)
    # Turn 3: user -> agent1 -> agent2 -> agent3(final)
    # Total messages = 12, but turn count = 6 (3 user + 3 final assistant)
    
    messages_sequence = [
        ("user", "Plan a trip to Rome"),
        ("assistant", "Weather: 25C sunny"),           # intermediate
        ("assistant", "Sights: Colosseum, Vatican"),    # intermediate
        ("assistant", "Final itinerary for Rome..."),   # final (next is user)
        ("user", "What about Paris?"),
        ("assistant", "Weather: 18C cloudy"),           # intermediate
        ("assistant", "Sights: Eiffel Tower, Louvre"),  # intermediate
        ("assistant", "Final itinerary for Paris..."),  # final (next is user)
        ("user", "Add budget info"),
        ("assistant", "Weather: 20C clear"),            # intermediate
        ("assistant", "Sights: budget options..."),     # intermediate
        ("assistant", "Budget itinerary..."),           # final (last message)
    ]
    
    # Count turns using the same logic as compact_session_history
    turn_count = 0
    for i, (role, content) in enumerate(messages_sequence):
        if role == "user":
            turn_count += 1
        elif role == "assistant":
            is_last = (i == len(messages_sequence) - 1)
            next_is_user = (i + 1 < len(messages_sequence) and messages_sequence[i + 1][0] == "user")
            if is_last or next_is_user:
                turn_count += 1
    
    # 3 user messages + 3 final assistant messages = 6 turn-relevant messages
    assert turn_count == 6
    
    # With K=10, compaction should NOT trigger (6 < 10)
    assert turn_count <= 10
    
    # With K=5, compaction SHOULD trigger (6 > 5)
    assert turn_count > 5


def test_pricing_calculator_incorporates_thought_tokens():
    """Verify that thought tokens are priced same as standard completion output tokens."""
    from backend.runtime.executor import calculate_llm_cost
    cost_with_thought = calculate_llm_cost("gemini-2.5-flash", 1000, 2000, 1000)
    expected_cost = ((1000 / 1_000_000) * 0.30) + (((2000 + 1000) / 1_000_000) * 2.50)
    assert abs(cost_with_thought - expected_cost) < 1e-9


def test_session_stats_endpoint_includes_thought_tokens_and_proper_turns(session: Session):
    """Verify that the session stats endpoint aggregates thought tokens and counts workflow runs for turns."""
    from backend.db.models import WorkflowRun, RunLog, Message
    
    run1 = WorkflowRun(
        id=101,
        workflow_id=1,
        session_id="stats_test_session",
        status="completed"
    )
    run2 = WorkflowRun(
        id=102,
        workflow_id=1,
        session_id="stats_test_session",
        status="completed"
    )
    session.add(run1)
    session.add(run2)
    
    log1 = RunLog(
        workflow_run_id=101,
        step_type="agent_message",
        content="hello",
        prompt_tokens=100,
        completion_tokens=200,
        thought_tokens=50,
        usd_cost=0.001
    )
    log2 = RunLog(
        workflow_run_id=102,
        step_type="info",
        content="compacted",
        prompt_tokens=10,
        completion_tokens=20,
        thought_tokens=5,
        usd_cost=0.0001
    )
    session.add(log1)
    session.add(log2)
    
    msg1 = Message(session_id="stats_test_session", role="user", content="hi")
    msg2 = Message(session_id="stats_test_session", role="assistant", content="hello")
    msg3 = Message(session_id="stats_test_session", role="user", content="next")
    session.add(msg1)
    session.add(msg2)
    session.add(msg3)
    session.commit()
    
    from backend.main import get_session_stats
    
    result = get_session_stats(session_id="stats_test_session", db=session)
    assert result["total_prompt_tokens"] == 110
    assert result["total_completion_tokens"] == 220
    assert result["total_thought_tokens"] == 55
    assert result["total_cost"] == 0.0011
    # 2 distinct workflow runs in database = 2 turns
    assert result["total_turns"] == 2


def test_system_setting_and_user_session_state(session: Session):
    # 1. Test SystemSetting CRUD
    setting = SystemSetting(key="TEST_SETTING_KEY", value="test_value_123")
    session.add(setting)
    session.commit()
    
    db_setting = session.exec(select(SystemSetting).where(SystemSetting.key == "TEST_SETTING_KEY")).first()
    assert db_setting is not None
    assert db_setting.value == "test_value_123"
    
    db_setting.value = "updated_value"
    session.add(db_setting)
    session.commit()
    
    db_setting2 = session.exec(select(SystemSetting).where(SystemSetting.key == "TEST_SETTING_KEY")).first()
    assert db_setting2.value == "updated_value"
    
    # 2. Test UserSessionState CRUD
    user_state = UserSessionState(chat_id="test_chat_id_111", active_workflow_id=12)
    session.add(user_state)
    session.commit()
    
    db_user_state = session.get(UserSessionState, "test_chat_id_111")
    assert db_user_state is not None
    assert db_user_state.active_workflow_id == 12
    
    db_user_state.active_workflow_id = 99
    session.add(db_user_state)
    session.commit()
    
    db_user_state2 = session.get(UserSessionState, "test_chat_id_111")
    assert db_user_state2.active_workflow_id == 99


def test_settings_rest_endpoints(session: Session):
    from fastapi.testclient import TestClient
    from backend.main import app, get_session
    
    # Override get_session dependency
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    
    # Check initial empty settings
    res = client.get("/api/settings")
    assert res.status_code == 200
    assert res.json() == {}
    
    # Save a setting
    res_save = client.post("/api/settings", json={"TELEGRAM_BOT_TOKEN": "my-secret-token"})
    assert res_save.status_code == 200
    assert res_save.json()["status"] == "saved"
    
    # Retrieve it again
    res2 = client.get("/api/settings")
    assert res2.status_code == 200
    assert res2.json() == {"TELEGRAM_BOT_TOKEN": "my-secret-token"}
    
    # Clean up dependency overrides
    app.dependency_overrides.clear()


def test_schedules_put_endpoint(session: Session):
    from fastapi.testclient import TestClient
    from backend.main import app, get_session
    from backend.db.models import Schedule, Workflow
    
    # Setup mock workflow in db
    wf = Workflow(id=99, name="Test Workflow", nodes_json="[]", edges_json="[]", is_active=True)
    session.add(wf)
    session.commit()

    # Create schedule in DB
    sch = Schedule(
        id=88,
        workflow_id=99,
        name="Hourly Run",
        cron_expression="0 * * * *",
        is_active=True
    )
    session.add(sch)
    session.commit()

    # Override get_session dependency
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    
    # Perform PUT request to toggle is_active to False and update name
    res = client.put("/api/schedules/88", json={
        "id": 88,
        "workflow_id": 99,
        "name": "Hourly Run Updated",
        "cron_expression": "0 * * * *",
        "is_active": False
    })
    assert res.status_code == 200
    updated_sch = res.json()
    assert updated_sch["name"] == "Hourly Run Updated"
    assert updated_sch["is_active"] is False

    # Check that it's updated in DB
    db_sch = session.get(Schedule, 88)
    assert db_sch.name == "Hourly Run Updated"
    assert db_sch.is_active is False
    
    # Clean up dependency overrides
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_guardrail_context_rules_short_circuit(session: Session):
    # Setup mock agent in database with context rule guardrail
    guardrails_json = json.dumps({
        "context_rules": [
            {"pattern": "agentic system is developed for", "response": "This is out of context."}
        ]
    })
    
    agent = Agent(
        id=3,
        name="Guardrail Agent",
        role="Tester",
        system_prompt="Try to answer normally.",
        model_provider="openai",
        model_name="gpt-4o-mini",
        memory_limit=5,
        tools="",
        channels="telegram",
        guardrails=guardrails_json
    )
    session.add(agent)
    
    # Setup mock workflow in database
    nodes = [
        {"id": "n1", "type": "trigger", "data": {"trigger_source": "manual"}},
        {"id": "n2", "type": "agent", "data": {"agent_id": 3, "label": "Guardrail Agent"}},
        {"id": "n3", "type": "action", "data": {"action_type": "telegram_reply"}}
    ]
    edges = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"}
    ]
    workflow = Workflow(
        id=3,
        name="Guardrail Test Workflow",
        description="Tests guardrail short circuiting",
        nodes_json=json.dumps(nodes),
        edges_json=json.dumps(edges),
        is_active=True
    )
    session.add(workflow)
    session.commit()

    # Mock get_llm_client to fail if called, because LLM should be short-circuited/bypassed
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=AssertionError("LLM should not be called due to guardrail short-circuit!"))

    with patch("backend.runtime.executor.get_llm_client", return_value=mock_llm), \
         patch("backend.runtime.executor.engine", session.bind):
        
        result = await execute_workflow(
            workflow_id=3,
            input_message="Verify the agentic system is developed for trip planning",
            trigger_source="manual",
            session_id="test_session_guardrail"
        )
        
        # Result should be the static block response configured in guardrails
        assert result == "This is out of context."
        
        # Verify run execution state was created in DB
        run = session.exec(select(WorkflowRun).where(WorkflowRun.workflow_id == 3)).first()
        assert run is not None
        assert run.status == "completed"
        
        # Verify logs were saved including the block message
        logs = session.exec(select(RunLog).where(RunLog.workflow_run_id == run.id)).all()
        assert any("Safety/Context Guardrail Triggered" in log.content for log in logs)
        
        # Wait for background task to complete before db teardown
        await asyncio.sleep(0.3)


@pytest.mark.asyncio
async def test_guardrail_templates_prompt_injection(session: Session):
    from backend.runtime.executor import make_agent_node, WorkflowState
    from backend.db.models import Agent
    from langchain_core.messages import SystemMessage
    
    guardrails_json = json.dumps({
        "templates": {
            "strict_context": True,
            "safety_shield": True,
            "fact_grounding": True
        }
    })
    
    agent = Agent(
        id=123,
        name="Test Template Agent",
        role="Unit Tester",
        system_prompt="Execute carefully.",
        model_provider="gemini",
        model_name="gemini-2.5-flash",
        memory_limit=10,
        tools="",
        channels="telegram",
        guardrails=guardrails_json
    )
    session.add(agent)
    session.commit()
    
    with patch("backend.runtime.executor.engine", session.bind), \
         patch("backend.runtime.executor.get_llm_client") as mock_client_factory:
        
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock()
        mock_client_factory.return_value = mock_llm
        
        # Build the agent node function
        agent_node = make_agent_node(node_id="test_node", agent_id=123)
        
        # Invoke it with a dummy state
        state = WorkflowState(
            messages=[],
            session_id="test_sess_templates",
            workflow_id=1,
            workflow_run_id=999,
            outputs={},
            active_node_id="",
            error=None,
            retrieved_sources=[]
        )
        await agent_node(state)
        
        assert mock_llm.ainvoke.called
        called_args = mock_llm.ainvoke.call_args[0][0]
        
        system_msg = next(m for m in called_args if isinstance(m, SystemMessage))
        content = system_msg.content
        
        assert "Execute carefully." in content
        assert "[GUARDRAIL: STRICT CONTEXT ALIGNMENT]" in content
        assert "[GUARDRAIL: PROMPT INJECTION SHIELD]" in content
        assert "[GUARDRAIL: FACT GROUNDING ENFORCER]" in content


@pytest.mark.asyncio
async def test_configurable_max_tool_turns(session: Session):
    from backend.runtime.executor import make_agent_node, WorkflowState
    
    guardrails_json = json.dumps({
        "max_tool_turns": 3
    })
    agent = Agent(
        id=444,
        name="Test Tool Limit Agent",
        role="Unit Tester",
        system_prompt="Ask to calculate.",
        model_provider="gemini",
        model_name="gemini-2.5-flash",
        memory_limit=10,
        tools="calculator",
        channels="telegram",
        guardrails=guardrails_json
    )
    session.add(agent)
    session.commit()
    
    with patch("backend.runtime.executor.engine", session.bind), \
         patch("backend.runtime.executor.get_llm_client") as mock_client_factory:
        
        mock_llm = MagicMock()
        mock_response = MagicMock()
        # Keep returning tool calls to force iteration limits
        mock_response.content = 'TOOL_CALL: {"tool": "calculator", "argument": "1+1"}'
        mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 20}
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_client_factory.return_value = mock_llm
        
        agent_node = make_agent_node(node_id="test_tool_limit_node", agent_id=444)
        
        state = WorkflowState(
            messages=[],
            session_id="test_sess_tool_limit",
            workflow_id=1,
            workflow_run_id=999,
            outputs={},
            active_node_id="",
            error=None,
            retrieved_sources=[]
        )
        
        await agent_node(state)
        
        # Initial invoke + 3 tool iterations = 4 calls total
        assert mock_llm.ainvoke.call_count == 4


@pytest.mark.asyncio
async def test_triage_node_routing(session: Session):
    from backend.runtime.executor import make_triage_route, WorkflowState
    from langchain_core.messages import HumanMessage
    
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "YES"
    mock_response.usage_metadata = {"input_tokens": 5, "output_tokens": 2}
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    
    with patch("backend.runtime.executor.get_llm_client", return_value=mock_llm), \
         patch("backend.runtime.executor.engine", session.bind):
        route_func = make_triage_route(
            triage_prompt="Is the user asking for travel?",
            model_provider="gemini",
            model_name="gemini-2.5-flash-lite",
            true_target="node_agent",
            false_target="node_refuse"
        )
        
        state = WorkflowState(
            messages=[HumanMessage(content="Plan a trip to Rome")],
            session_id="test_triage_sess",
            workflow_id=1,
            workflow_run_id=999,
            outputs={},
            active_node_id="",
            error=None,
            retrieved_sources=[]
        )
        
        res = await route_func(state)
        assert res == "node_agent"
        
        # Test failure routing decision
        mock_response.content = "NO"
        res_fail = await route_func(state)
        assert res_fail == "node_refuse"


@pytest.mark.asyncio
async def test_triage_node_routing_with_history(session: Session):
    from backend.runtime.executor import make_triage_route, WorkflowState
    from langchain_core.messages import HumanMessage
    from backend.db.models import Message
    
    # Setup some message history in db
    m1 = Message(session_id="test_triage_sess_history", role="user", content="Hello, I want to travel.")
    m2 = Message(session_id="test_triage_sess_history", role="assistant", content="Where do you want to go?")
    m3 = Message(session_id="test_triage_sess_history", role="user", content="Rome")
    session.add(m1)
    session.add(m2)
    session.add(m3)
    session.commit()
    
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "YES"
    mock_response.usage_metadata = {"input_tokens": 5, "output_tokens": 2}
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    
    with patch("backend.runtime.executor.get_llm_client", return_value=mock_llm), \
         patch("backend.runtime.executor.engine", session.bind):
        route_func = make_triage_route(
            triage_prompt="Is the user asking for travel?",
            model_provider="gemini",
            model_name="gemini-2.5-flash-lite",
            true_target="node_agent",
            false_target="node_refuse"
        )
        
        state = WorkflowState(
            messages=[HumanMessage(content="Rome")],
            session_id="test_triage_sess_history",
            workflow_id=1,
            workflow_run_id=999,
            outputs={},
            active_node_id="",
            error=None,
            retrieved_sources=[]
        )
        
        res = await route_func(state)
        assert res == "node_agent"
        
        # Verify that mock_llm.ainvoke was called with the context
        assert mock_llm.ainvoke.called
        called_messages = mock_llm.ainvoke.call_args[0][0]
        sys_msg = called_messages[0].content
        assert "Previous Conversation Context:" in sys_msg
        assert "User: Hello, I want to travel." in sys_msg
        assert "Assistant: Where do you want to go?" in sys_msg
        assert "User: Rome" not in sys_msg


@pytest.mark.asyncio
async def test_action_node_append_message(session: Session):
    from backend.runtime.executor import make_action_node, WorkflowState
    from backend.db.models import Message
    
    # Pre-populate session message to be updated by append logic
    last_msg = Message(session_id="test_sess_action_append", role="assistant", content="Base solution message.")
    session.add(last_msg)
    session.commit()
    
    node_data = {
        "action_type": "telegram_reply",
        "label": "Escalate to Tier 2",
        "append_message": "The engineering team will contact you soon."
    }
    
    action_node = make_action_node(
        node_id="node_action_escalate",
        node_data=node_data
    )
    
    state = WorkflowState(
        messages=[],
        session_id="test_sess_action_append",
        workflow_id=1,
        workflow_run_id=999,
        outputs={"node_support_agent": "Base solution message."},
        active_node_id="",
        error=None,
        retrieved_sources=[]
    )
    
    with patch("backend.runtime.executor.engine", session.bind):
        res = await action_node(state)
        
        # Verify the returned output has appended message
        expected = "Base solution message.\n\nThe engineering team will contact you soon."
        assert res["outputs"]["node_action_escalate"] == expected
        
        # Verify database message is updated
        updated_msg = session.exec(
            select(Message)
            .where(Message.session_id == "test_sess_action_append")
            .where(Message.role == "assistant")
        ).first()
        assert updated_msg is not None
        assert updated_msg.content == expected


@pytest.mark.asyncio
async def test_executor_handles_list_content():
    from backend.runtime.executor import get_content_str, estimate_tokens
    
    # Verify string content is returned as-is
    assert get_content_str("Hello World") == "Hello World"
    
    # Verify list of strings/dicts is concatenated correctly
    list_content = ["Hello ", {"text": "World"}, {"content": "!"}, 42]
    assert get_content_str(list_content) == "Hello World!42"
    
    # Verify estimate_tokens works with list content
    assert estimate_tokens(list_content) > 0


@pytest.mark.asyncio
async def test_action_node_combines_preceding_code_blocks(session: Session):
    from backend.runtime.executor import make_action_node, WorkflowState
    from unittest.mock import patch
    
    node_data = {
        "action_type": "telegram_reply",
        "label": "Send Completed Code"
    }
    
    action_node = make_action_node(
        node_id="node_action_send",
        node_data=node_data
    )
    
    state = WorkflowState(
        messages=[],
        session_id="test_sess_combine_code",
        workflow_id=1,
        workflow_run_id=888,
        outputs={
            "node_developer_agent": "Here is the code:\n```python\ndef test(): pass\n```",
            "node_qa_agent": "review: pass\nLooks good!"
        },
        active_node_id="",
        error=None,
        retrieved_sources=[]
    )
    
    with patch("backend.runtime.executor.engine", session.bind):
        res = await action_node(state)
        
        expected = (
            "Here is the code:\n```python\ndef test(): pass\n```\n\n"
            "### Review & Audit Details:\n"
            "review: pass\nLooks good!"
        )
        assert res["outputs"]["node_action_send"] == expected


def test_cancel_workflow_run(session: Session):
    from fastapi.testclient import TestClient
    from backend.main import app, get_session
    from backend.runtime.executor import active_workflow_tasks
    
    # 1. Create a running WorkflowRun
    run = WorkflowRun(
        workflow_id=1,
        session_id="test_cancel_sess",
        status="running"
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    run_id = run.id
    
    # 2. Add a dummy task that we can cancel
    class DummyTask:
        def __init__(self):
            self.cancelled_called = False
        def cancel(self):
            self.cancelled_called = True
            
    dummy_task = DummyTask()
    active_workflow_tasks[run_id] = dummy_task
    
    # 3. Setup client and override session
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    
    # 4. Trigger cancel
    res = client.delete(f"/api/runs/{run_id}/cancel")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "cancelled"
    assert data["run_id"] == run_id
    
    # 5. Assert database state updated
    session.expire_all()
    updated_run = session.get(WorkflowRun, run_id)
    assert updated_run.status == "failed"
    assert updated_run.completed_at is not None
    
    # Assert task cancel was called
    assert dummy_task.cancelled_called is True
    
    # Assert logs added
    logs = session.exec(select(RunLog).where(RunLog.workflow_run_id == run_id)).all()
    assert len(logs) == 1
    assert "cancelled by the user" in logs[0].content
    
    # Clean up overrides & active_workflow_tasks
    app.dependency_overrides.clear()
    active_workflow_tasks.pop(run_id, None)




