import json
from sqlmodel import Session, select
from backend.db.database import engine
from backend.db.models import Agent, Workflow, Schedule

def seed_database():
    with Session(engine) as session:
        # Check if database is already seeded
        agent_exists = session.exec(select(Agent)).first()
        if agent_exists:
            # Migration check: update existing Weather Expert agent tools and prompts for all agents to be concise
            weather_agent_db = session.exec(select(Agent).where(Agent.name == "Weather Expert")).first()
            if weather_agent_db:
                weather_agent_db.tools = "weather"
                weather_agent_db.system_prompt = "Check the weather using the 'weather' tool. Summarize current conditions concisely. Keep it under 80 words."
                session.add(weather_agent_db)
                
            guide_agent_db = session.exec(select(Agent).where(Agent.name == "Local Tour Guide")).first()
            if guide_agent_db:
                guide_agent_db.system_prompt = "Find top 3 local attractions and sightseeing spots for the destination using web search. Keep your findings highly summarized and under 120 words."
                session.add(guide_agent_db)
                
            consolidator_agent_db = session.exec(select(Agent).where(Agent.name == "Travel Coordinator")).first()
            if consolidator_agent_db:
                consolidator_agent_db.system_prompt = "Combine the weather forecast and sightseeing attractions into a neat, concise 3-day travel itinerary. Be brief and structured. Limit your total response to 250 words."
                session.add(consolidator_agent_db)
                
            # Migration: Remove old summarizer workflow if exists
            old_wf = session.exec(select(Workflow).where(Workflow.name == "Autonomous Research & Summarization")).first()
            if old_wf:
                # Remove any schedules linked to it first
                old_schedules = session.exec(select(Schedule).where(Schedule.workflow_id == old_wf.id)).all()
                for sch in old_schedules:
                    session.delete(sch)
                session.delete(old_wf)
                
            # Migration: Remove old summarizer agents if they exist
            old_researcher = session.exec(select(Agent).where(Agent.name == "Web Researcher")).first()
            if old_researcher:
                session.delete(old_researcher)
            old_summarizer = session.exec(select(Agent).where(Agent.name == "Executive Summarizer")).first()
            if old_summarizer:
                session.delete(old_summarizer)
                
            # Migration: Seed new AI News agents if they don't exist
            news_collector = session.exec(select(Agent).where(Agent.name == "AI News Collector")).first()
            if not news_collector:
                news_collector = Agent(
                    name="AI News Collector",
                    role="News Gatherer",
                    system_prompt="Find the top 5 most viral news articles about AI tech giants: Google, Microsoft, OpenAI, Anthropic, Meta. Retrieve titles and URLs using search.",
                    model_provider="gemini",
                    model_name="gemini-2.5-flash",
                    tools="search",
                    channels="telegram",
                    guardrails="{}"
                )
                session.add(news_collector)
                
            news_summarizer = session.exec(select(Agent).where(Agent.name == "AI News Summarizer")).first()
            if not news_summarizer:
                news_summarizer = Agent(
                    name="AI News Summarizer",
                    role="Briefing Writer",
                    system_prompt="Compile the top 5 AI news articles into a bulleted markdown digest. Keep summaries short (under 250 words total) and cite titles and URLs.",
                    model_provider="gemini",
                    model_name="gemini-2.5-flash",
                    tools="",
                    channels="telegram",
                    guardrails="{}"
                )
                session.add(news_summarizer)
            
            session.commit()
            if news_collector.id is None:
                session.refresh(news_collector)
            if news_summarizer.id is None:
                session.refresh(news_summarizer)
                
            # Migration: Ensure single "AI News Digest" workflow with Telegram Trigger exists
            # We check if both or either exists, and consolidate if necessary.
            sched_news_wf = session.exec(select(Workflow).where(Workflow.name == "Scheduled AI News Digest")).first()
            news_wf = session.exec(select(Workflow).where(Workflow.name == "AI News Digest")).first()
            
            # If the duplicate "Scheduled AI News Digest" exists OR the standard one does not exist,
            # we delete both and recreate a single "AI News Digest" with a Telegram Trigger.
            if sched_news_wf or not news_wf:
                for wf in [sched_news_wf, news_wf]:
                    if wf:
                        schedules_to_del = session.exec(select(Schedule).where(Schedule.workflow_id == wf.id)).all()
                        for sch in schedules_to_del:
                            session.delete(sch)
                        session.delete(wf)
                session.commit()

                t2_nodes = [
                    {"id": "node_trigger", "type": "trigger", "position": {"x": 50, "y": 200}, "data": {"label": "Telegram Message Trigger", "trigger_source": "telegram"}},
                    {"id": "node_collector", "type": "agent", "position": {"x": 250, "y": 200}, "data": {"label": "AI News Collector", "agent_id": news_collector.id}},
                    {"id": "node_summarizer", "type": "agent", "position": {"x": 450, "y": 200}, "data": {"label": "AI News Summarizer", "agent_id": news_summarizer.id}},
                    {"id": "node_action_notify", "type": "action", "position": {"x": 650, "y": 200}, "data": {"label": "Post News to Telegram", "action_type": "telegram_reply"}}
                ]
                t2_edges = [
                    {"id": "e_trigger_collector", "source": "node_trigger", "target": "node_collector"},
                    {"id": "e_collector_summarizer", "source": "node_collector", "target": "node_summarizer"},
                    {"id": "e_summarizer_notify", "source": "node_summarizer", "target": "node_action_notify"}
                ]
                news_wf = Workflow(
                    name="AI News Digest",
                    description="One agent gathers the latest viral news about AI tech giants using web search, and another drafts a short markdown digest to post directly back to the user via Telegram.",
                    nodes_json=json.dumps(t2_nodes),
                    edges_json=json.dumps(t2_edges),
                    is_active=True
                )
                session.add(news_wf)
                session.commit()
            # Migration: Ensure Support Specialist agent exists
            support_agent_db = session.exec(select(Agent).where(Agent.name == "Support Specialist")).first()
            if not support_agent_db:
                support_agent_db = Agent(
                    name="Support Specialist",
                    role="Technical Support Expert",
                    system_prompt="Analyze the user's issue and suggest a resolution. If the issue is a complex bug, database crash, security leak, system down error, or billing discrepancy requiring human Tier 2 engineer intervention, append 'escalate: yes' to your response. Otherwise, append 'escalate: no'. Keep answers under 150 words.",
                    model_provider="gemini",
                    model_name="gemini-2.5-flash",
                    tools="search",
                    channels="telegram",
                    guardrails="{}"
                )
                session.add(support_agent_db)
                session.commit()
                session.refresh(support_agent_db)

            # Migration: Rename and update Template 1 (Lead Triage & Auto-Responder) to Smart Support Escalation Router
            t1_wf_db = session.exec(select(Workflow).where(Workflow.id == 1)).first()
            if t1_wf_db and (t1_wf_db.name == "Lead Triage & Auto-Responder" or t1_wf_db.name == "Smart Support Escalation Router"):
                t1_nodes = [
                    {"id": "node_trigger", "type": "trigger", "position": {"x": 50, "y": 180}, "data": {"label": "Telegram Message Trigger", "trigger_source": "telegram"}},
                    {"id": "node_triage", "type": "triage", "position": {"x": 260, "y": 180}, "data": {"label": "Triage: Is support query?", "triage_prompt": "Is the query related to a technical issue, bug, system error, billing question, or support ticket?", "model_provider": "gemini", "model_name": "gemini-2.5-flash-lite"}},
                    {"id": "node_support_agent", "type": "agent", "position": {"x": 480, "y": 80}, "data": {"label": "Support Specialist", "agent_id": support_agent_db.id}},
                    {"id": "node_condition", "type": "condition", "position": {"x": 720, "y": 80}, "data": {"label": "Is Escalation Needed?", "expression": "escalate: yes"}},
                    {"id": "node_action_escalate", "type": "action", "position": {"x": 940, "y": 0}, "data": {"label": "Escalate to Tier 2", "action_type": "telegram_reply", "append_message": "The team will be reaching out to you soon regarding the same."}},
                    {"id": "node_action_resolve", "type": "action", "position": {"x": 940, "y": 160}, "data": {"label": "Send Resolution", "action_type": "telegram_reply"}},
                    {"id": "node_archive_general", "type": "action", "position": {"x": 480, "y": 320}, "data": {"label": "Log & Archive Message", "action_type": "archive", "archive_message": "Logged as non-support message. Thank you!"}}
                ]
                t1_edges = [
                    {"id": "e_trigger_triage", "source": "node_trigger", "target": "node_triage"},
                    {"id": "e_triage_support", "source": "node_triage", "target": "node_support_agent", "sourceHandle": "true"},
                    {"id": "e_triage_archive", "source": "node_triage", "target": "node_archive_general", "sourceHandle": "false"},
                    {"id": "e_support_cond", "source": "node_support_agent", "target": "node_condition"},
                    {"id": "e_cond_escalate", "source": "node_condition", "target": "node_action_escalate", "sourceHandle": "true"},
                    {"id": "e_cond_resolve", "source": "node_condition", "target": "node_action_resolve", "sourceHandle": "false"}
                ]
                t1_wf_db.name = "Smart Support Escalation Router"
                t1_wf_db.description = "Incoming queries are routed by a semantic triage node. Support queries are handled by a Support Specialist agent. If it flags the issue as a complex technical bug, a Tier-2 escalation is triggered, otherwise a direct resolution is sent. Non-support queries are archived."
                t1_wf_db.nodes_json = json.dumps(t1_nodes)
                t1_wf_db.edges_json = json.dumps(t1_edges)
                session.add(t1_wf_db)
                session.commit()

            print("Successfully migrated existing database to Smart Support Escalation Router.")
            return

        print("Seeding database with default agents and pre-built templates...")

        # 1. Create Default Agents
        triage_agent = Agent(
            name="Lead Classifier",
            role="Triage Agent",
            system_prompt="Analyze the incoming customer request. Categorize it as 'Enterprise' or 'Spam'. Reply with exactly one of those words.",
            model_provider="gemini",
            model_name="gemini-2.5-flash",
            tools="",
            channels="telegram",
            guardrails=json.dumps({"max_turns": 2})
        )

        pitch_agent = Agent(
            name="Sales Specialist",
            role="Enterprise Pitch Writer",
            system_prompt="Write a professional, high-converting sales pitch based on the lead's company info and request.",
            model_provider="gemini",
            model_name="gemini-2.5-flash",
            tools="search",
            channels="telegram",
            guardrails="{}"
        )

        news_collector = Agent(
            name="AI News Collector",
            role="News Gatherer",
            system_prompt="Find the top 5 most viral news articles about AI tech giants: Google, Microsoft, OpenAI, Anthropic, Meta. Retrieve titles and URLs using search.",
            model_provider="gemini",
            model_name="gemini-2.5-flash",
            tools="search",
            channels="telegram",
            guardrails="{}"
        )

        news_summarizer = Agent(
            name="AI News Summarizer",
            role="Briefing Writer",
            system_prompt="Compile the top 5 AI news articles into a bulleted markdown digest. Keep summaries short (under 250 words total) and cite titles and URLs.",
            model_provider="gemini",
            model_name="gemini-2.5-flash",
            tools="",
            channels="telegram",
            guardrails="{}"
        )

        weather_agent = Agent(
            name="Weather Expert",
            role="Weather Forecaster",
            system_prompt="Check the weather using the 'weather' tool. Summarize current conditions concisely. Keep it under 80 words.",
            model_provider="gemini",
            model_name="gemini-2.5-flash",
            tools="weather",
            channels="telegram",
            guardrails="{}"
        )

        guide_agent = Agent(
            name="Local Tour Guide",
            role="Sightseeing Specialist",
            system_prompt="Find top 3 local attractions and sightseeing spots for the destination using web search. Keep your findings highly summarized and under 120 words.",
            model_provider="gemini",
            model_name="gemini-2.5-flash",
            tools="search",
            channels="telegram",
            guardrails="{}"
        )

        consolidator_agent = Agent(
            name="Travel Coordinator",
            role="Itinerary Planner",
            system_prompt="Combine the weather forecast and sightseeing attractions into a neat, concise 3-day travel itinerary. Be brief and structured. Limit your total response to 250 words.",
            model_provider="gemini",
            model_name="gemini-2.5-flash",
            tools="",
            channels="telegram",
            guardrails="{}"
        )

        support_agent = Agent(
            name="Support Specialist",
            role="Technical Support Expert",
            system_prompt="Analyze the user's issue and suggest a resolution. If the issue is a complex bug, database crash, security leak, system down error, or billing discrepancy requiring human Tier 2 engineer intervention, append 'escalate: yes' to your response. Otherwise, append 'escalate: no'. Keep answers under 150 words.",
            model_provider="gemini",
            model_name="gemini-2.5-flash",
            tools="search",
            channels="telegram",
            guardrails="{}"
        )

        session.add(triage_agent)
        session.add(pitch_agent)
        session.add(news_collector)
        session.add(news_summarizer)
        session.add(weather_agent)
        session.add(guide_agent)
        session.add(consolidator_agent)
        session.add(support_agent)
        session.commit()

        # Refresh objects to get IDs
        session.refresh(triage_agent)
        session.refresh(pitch_agent)
        session.refresh(news_collector)
        session.refresh(news_summarizer)
        session.refresh(weather_agent)
        session.refresh(guide_agent)
        session.refresh(consolidator_agent)
        session.refresh(support_agent)

        # 2. Seed Pre-Built Templates
        
        # Template 1: Smart Support Escalation Router
        t1_nodes = [
            {"id": "node_trigger", "type": "trigger", "position": {"x": 50, "y": 180}, "data": {"label": "Telegram Message Trigger", "trigger_source": "telegram"}},
            {"id": "node_triage", "type": "triage", "position": {"x": 260, "y": 180}, "data": {"label": "Triage: Is support query?", "triage_prompt": "Is the query related to a technical issue, bug, system error, billing question, or support ticket?", "model_provider": "gemini", "model_name": "gemini-2.5-flash-lite"}},
            {"id": "node_support_agent", "type": "agent", "position": {"x": 480, "y": 80}, "data": {"label": "Support Specialist", "agent_id": support_agent.id}},
            {"id": "node_condition", "type": "condition", "position": {"x": 720, "y": 80}, "data": {"label": "Is Escalation Needed?", "expression": "escalate: yes"}},
            {"id": "node_action_escalate", "type": "action", "position": {"x": 940, "y": 0}, "data": {"label": "Escalate to Tier 2", "action_type": "telegram_reply", "append_message": "The team will be reaching out to you soon regarding the same."}},
            {"id": "node_action_resolve", "type": "action", "position": {"x": 940, "y": 160}, "data": {"label": "Send Resolution", "action_type": "telegram_reply"}},
            {"id": "node_archive_general", "type": "action", "position": {"x": 480, "y": 320}, "data": {"label": "Log & Archive Message", "action_type": "archive", "archive_message": "Logged as non-support message. Thank you!"}}
        ]
        t1_edges = [
            {"id": "e_trigger_triage", "source": "node_trigger", "target": "node_triage"},
            {"id": "e_triage_support", "source": "node_triage", "target": "node_support_agent", "sourceHandle": "true"},
            {"id": "e_triage_archive", "source": "node_triage", "target": "node_archive_general", "sourceHandle": "false"},
            {"id": "e_support_cond", "source": "node_support_agent", "target": "node_condition"},
            {"id": "e_cond_escalate", "source": "node_condition", "target": "node_action_escalate", "sourceHandle": "true"},
            {"id": "e_cond_resolve", "source": "node_condition", "target": "node_action_resolve", "sourceHandle": "false"}
        ]
        template1 = Workflow(
            name="Smart Support Escalation Router",
            description="Incoming queries are routed by a semantic triage node. Support queries are handled by a Support Specialist agent. If it flags the issue as a complex technical bug, a Tier-2 escalation is triggered, otherwise a direct resolution is sent. Non-support queries are archived.",
            nodes_json=json.dumps(t1_nodes),
            edges_json=json.dumps(t1_edges),
            is_active=True
        )

        # Template 2: AI News Digest
        t2_nodes = [
            {"id": "node_trigger", "type": "trigger", "position": {"x": 50, "y": 200}, "data": {"label": "Telegram Message Trigger", "trigger_source": "telegram"}},
            {"id": "node_collector", "type": "agent", "position": {"x": 250, "y": 200}, "data": {"label": "AI News Collector", "agent_id": news_collector.id}},
            {"id": "node_summarizer", "type": "agent", "position": {"x": 450, "y": 200}, "data": {"label": "AI News Summarizer", "agent_id": news_summarizer.id}},
            {"id": "node_action_notify", "type": "action", "position": {"x": 650, "y": 200}, "data": {"label": "Post News to Telegram", "action_type": "telegram_reply"}}
        ]
        t2_edges = [
            {"id": "e_trigger_collector", "source": "node_trigger", "target": "node_collector"},
            {"id": "e_collector_summarizer", "source": "node_collector", "target": "node_summarizer"},
            {"id": "e_summarizer_notify", "source": "node_summarizer", "target": "node_action_notify"}
        ]
        template2 = Workflow(
            name="AI News Digest",
            description="One agent gathers the latest viral news about AI tech giants using web search, and another drafts a short markdown digest to post directly back to the user via Telegram.",
            nodes_json=json.dumps(t2_nodes),
            edges_json=json.dumps(t2_edges),
            is_active=True
        )

        # Template 3: Asynchronous Parallel Travel Planner
        t3_nodes = [
            {"id": "node_trigger", "type": "trigger", "position": {"x": 50, "y": 200}, "data": {"label": "Telegram Message Trigger", "trigger_source": "telegram"}},
            {"id": "node_weather", "type": "agent", "position": {"x": 250, "y": 100}, "data": {"label": "Weather Expert", "agent_id": weather_agent.id}},
            {"id": "node_guide", "type": "agent", "position": {"x": 250, "y": 300}, "data": {"label": "Local Tour Guide", "agent_id": guide_agent.id}},
            {"id": "node_consolidator", "type": "agent", "position": {"x": 480, "y": 200}, "data": {"label": "Travel Coordinator", "agent_id": consolidator_agent.id}},
            {"id": "node_action_reply", "type": "action", "position": {"x": 700, "y": 200}, "data": {"label": "Send Itinerary via Telegram", "action_type": "telegram_reply"}}
        ]
        t3_edges = [
            {"id": "e_trigger_weather", "source": "node_trigger", "target": "node_weather"},
            {"id": "e_trigger_guide", "source": "node_trigger", "target": "node_guide"},
            {"id": "e_weather_con", "source": "node_weather", "target": "node_consolidator"},
            {"id": "e_guide_con", "source": "node_guide", "target": "node_consolidator"},
            {"id": "e_con_reply", "source": "node_consolidator", "target": "node_action_reply"}
        ]
        template3 = Workflow(
            name="Parallel Travel Planner",
            description="A user request in Telegram spawns parallel checks: one agent checks the weather, another searches sights, and a final agent compiles a personalized 3-day itinerary.",
            nodes_json=json.dumps(t3_nodes),
            edges_json=json.dumps(t3_edges),
            is_active=True
        )

        session.add(template1)
        session.add(template2)
        session.add(template3)
        session.commit()
        
        session.refresh(template2)
        
        print("Database successfully seeded with default agents and workflows.")
