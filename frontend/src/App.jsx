import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  ReactFlow, 
  Background, 
  Controls, 
  useNodesState, 
  useEdgesState, 
  addEdge
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { 
  Bot, 
  GitFork, 
  History, 
  Calendar, 
  Play, 
  Pause,
  Plus, 
  Trash2, 
  Cpu, 
  Terminal, 
  Coins, 
  Activity, 
  CheckCircle, 
  XCircle, 
  AlertTriangle,
  RefreshCw,
  Search,
  BookOpen,
  Settings,
  Square
} from 'lucide-react';

import { nodeTypes } from './components/nodes/CustomNodes';

const modelsByProvider = {
  gemini: [
    'gemini-2.5-flash',
    'gemini-2.5-pro',
    'gemini-2.5-flash-lite',
    'gemini-3.5-flash',
    'gemini-3.1-pro-preview',
    'gemini-3.1-flash-lite',
    'gemini-2.0-flash',
    'gemini-2.0-flash-thinking'
  ],
  openai: [
    'gpt-4o-mini',
    'gpt-4o',
    'gpt-5-mini',
    'gpt-5',
    'gpt-5.4-mini',
    'gpt-5.4'
  ]
};

const availableTools = [
  { id: 'search', name: 'Web Search' },
  { id: 'calculator', name: 'Calculator' },
  { id: 'sandbox_io', name: 'Sandbox File IO' },
  { id: 'weather', name: 'Real-time Weather' }
];

const toolInfo = {
  search: "Web Search & Scrape: Searches DuckDuckGo for live facts. If argument starts with http:// or https://, it scrapes the clean text content of the page instead.",
  calculator: "Calculator: Computes mathematical expressions safely.",
  sandbox_io: "Sandbox File IO: Reads/writes files in a secure workspace directory.",
  weather: "Weather: Fetches live temperature and conditions for any city."
};

export default function App() {
  const [activeTab, setActiveTab] = useState('workflows');
  
  // Data States
  const [agents, setAgents] = useState([]);
  const [workflows, setWorkflows] = useState([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState(null);
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [runsPage, setRunsPage] = useState(1);
  const [schedules, setSchedules] = useState([]);
  const [workflowMemory, setWorkflowMemory] = useState([]);

  // React Flow state bindings
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Form states
  const [agentForm, setAgentForm] = useState({
    name: '', role: '', system_prompt: '', model_provider: 'gemini',
    model_name: 'gemini-2.5-flash', memory_limit: 10, tools: '', channels: 'telegram', guardrails: '{}'
  });
  const [editingAgentId, setEditingAgentId] = useState(null);
  const [editingScheduleId, setEditingScheduleId] = useState(null);

  // Node Editing Modal state
  const [isNodeEditModalOpen, setIsNodeEditModalOpen] = useState(false);
  const [editingNode, setEditingNode] = useState(null);
  const [nodeEditForm, setNodeEditForm] = useState({
    label: '',
    trigger_source: 'telegram',
    agent_id: '',
    expression: '',
    triage_prompt: '',
    model_provider: 'gemini',
    model_name: 'gemini-2.5-flash-lite',
    action_type: 'telegram_reply',
    archive_message: 'Thank you, your message has been logged/archived.'
  });
  
  const [workflowForm, setWorkflowForm] = useState({ name: '', description: '' });
  const [scheduleForm, setScheduleForm] = useState({ workflow_id: '', name: '', cron_expression: '*/5 * * * *', chat_id: '' });
  const [testInput, setTestInput] = useState('Plan a 3-day trip to Rome');

  // Settings Credentials State
  const [settingsForm, setSettingsForm] = useState({
    TELEGRAM_BOT_TOKEN: '',
    GEMINI_API_KEY: '',
    OPENAI_API_KEY: '',
    SLACK_BOT_TOKEN: '',
    WHATSAPP_ACCESS_TOKEN: '',
    WHATSAPP_PHONE_NUMBER_ID: '',
    WHATSAPP_VERIFY_TOKEN: ''
  });

  // Guardrails Configuration States
  const [guardrailMaxTurns, setGuardrailMaxTurns] = useState('10');
  const [guardrailTokenCap, setGuardrailTokenCap] = useState('180000');
  const [guardrailMaxToolTurns, setGuardrailMaxToolTurns] = useState('5');
  const [guardrailKeywords, setGuardrailKeywords] = useState('');
  const [guardrailContextRules, setGuardrailContextRules] = useState([]);
  const [guardrailTemplates, setGuardrailTemplates] = useState({
    strict_context: false,
    safety_shield: false,
    fact_grounding: false
  });
  const [newRulePattern, setNewRulePattern] = useState('');
  const [newRuleResponse, setNewRuleResponse] = useState('');
  const [currentSessionId, setCurrentSessionId] = useState(() => `manual_${Date.now()}`);
  const [sessionStats, setSessionStats] = useState(null);

  // WebSocket Live Observability States
  const [wsLogs, setWsLogs] = useState([]);
  const [wsStats, setWsStats] = useState({ promptTokens: 0, completionTokens: 0, thoughtTokens: 0, cost: 0.0 });
  const [wsActiveNode, setWsActiveNode] = useState(null);
  const [activeRunId, setActiveRunId] = useState(null);
  const [isWsConnected, setIsWsConnected] = useState(false);
  const wsRef = useRef(null);
  const logsEndRef = useRef(null);

  const fetchSessionStats = async (sessionId) => {
    if (!sessionId) {
      setSessionStats(null);
      return;
    }
    try {
      const res = await fetch(`/api/sessions/${sessionId}/stats`);
      const data = await res.json();
      setSessionStats(data);
    } catch (err) {
      console.error("Failed to load session stats:", err);
    }
  };

  useEffect(() => {
    fetchSessionStats(currentSessionId);
  }, [currentSessionId]);

  // Load API Data
  const fetchData = async () => {
    try {
      const [agentsRes, workflowsRes, runsRes, schedulesRes] = await Promise.all([
        fetch('/api/agents').then(r => r.json()),
        fetch('/api/workflows').then(r => r.json()),
        fetch('/api/runs').then(r => r.json()),
        fetch('/api/schedules').then(r => r.json())
      ]);
      setAgents(agentsRes);
      setWorkflows(workflowsRes);
      setRuns(runsRes);
      setSchedules(schedulesRes);
    } catch (err) {
      console.error("Failed to fetch data:", err);
    }
  };

  const fetchSettings = async () => {
    try {
      const res = await fetch('/api/settings');
      const data = await res.json();
      setSettingsForm(prev => ({
        ...prev,
        ...data
      }));
    } catch (err) {
      console.error("Failed to load settings:", err);
    }
  };

  useEffect(() => {
    fetchData();
    fetchSettings();
  }, []);

  // Auto-select first workflow when workflows load for the first time
  const hasSelectedDefault = useRef(false);
  useEffect(() => {
    if (workflows.length > 0 && !hasSelectedDefault.current) {
      handleSelectWorkflow(workflows[0]);
      hasSelectedDefault.current = true;
    }
  }, [workflows]);

  // Connect WebSocket
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/monitoring`;
    
    const connectWS = () => {
      console.log("[WebSocket] Connecting to", wsUrl);
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        setIsWsConnected(true);
        console.log("[WebSocket] Connected successfully");
      };
      
      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        
        if (msg.type === 'workflow_started') {
          setWsLogs([]);
          setWsStats({ promptTokens: 0, completionTokens: 0, thoughtTokens: 0, cost: 0.0 });
          setWsActiveNode(null);
          setActiveRunId(msg.workflow_run_id);
        }
        
        else if (msg.type === 'node_active') {
          setWsActiveNode(msg.node_id);
          // Auto highlight visual canvas node state
          setNodes((nds) => 
            nds.map((n) => ({
              ...n,
              className: n.id === msg.node_id ? 'active-node' : ''
            }))
          );
        }
        
        else if (msg.type === 'log') {
          setWsLogs(prev => [...prev, msg]);
          if (msg.tokens) {
            setWsStats(prev => ({
              promptTokens: prev.promptTokens + msg.tokens.prompt,
              completionTokens: prev.completionTokens + msg.tokens.completion,
              thoughtTokens: prev.thoughtTokens + (msg.tokens.thought || 0),
              cost: prev.cost + (msg.cost || 0.0)
            }));
          }
        }
        
        else if (msg.type === 'workflow_completed') {
          setWsActiveNode(null);
          setActiveRunId(null);
          setNodes((nds) => nds.map((n) => ({ ...n, className: '' })));
          fetchData(); // Refresh histories & memories
          fetchSessionStats(currentSessionId);
          if (selectedWorkflow) {
            fetchWorkflowMemory(selectedWorkflow.id);
          }
        }
      };
      
      ws.onclose = () => {
        setIsWsConnected(false);
        console.log("[WebSocket] Disconnected. Reconnecting in 3s...");
        setTimeout(connectWS, 3000);
      };
      
      wsRef.current = ws;
    };

    connectWS();
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [selectedWorkflow]);

  // Auto-scroll logs terminal
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [wsLogs]);

  // Load selected workflow memory
  const fetchWorkflowMemory = async (workflowId) => {
    try {
      const res = await fetch(`/api/workflows/${workflowId}/memory`);
      const data = await res.json();
      setWorkflowMemory(data);
    } catch (err) {
      console.error("Failed to load memory:", err);
    }
  };

  const handleSelectWorkflow = (wf) => {
    setSelectedWorkflow(wf);
    fetchWorkflowMemory(wf.id);
    
    // Parse React Flow nodes & edges
    try {
      const parsedNodes = JSON.parse(wf.nodes_json || '[]');
      const parsedEdges = JSON.parse(wf.edges_json || '[]');
      
      // Inject label and agent config detail into the visual nodes
      const enrichedNodes = parsedNodes.map(node => {
        if (node.type === 'agent' && node.data.agent_id) {
          const matchedAgent = agents.find(a => a.id === node.data.agent_id);
          if (matchedAgent) {
            node.data = {
              ...node.data,
              label: matchedAgent.name,
              agent_role: matchedAgent.role,
              model_name: matchedAgent.model_name
            };
          }
        }
        return node;
      });

      setNodes(enrichedNodes);
      setEdges(parsedEdges);
    } catch (e) {
      setNodes([]);
      setEdges([]);
    }
  };

  // Run visual workflow manually
  const handleRunWorkflow = async () => {
    if (!selectedWorkflow) return;
    setWsLogs([{ step_type: 'agent_thought', content: 'Initializing execution run request...' }]);
    try {
      await fetch(`/api/workflows/${selectedWorkflow.id}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: testInput, session_id: currentSessionId })
      });
    } catch (err) {
      console.error(err);
    }
  };

  // Cancel currently running workflow
  const handleCancelWorkflow = async (runId) => {
    if (!runId) return;
    try {
      setWsLogs(prev => [...prev, { step_type: 'error', content: '[Cancellation] Sending cancellation request...' }]);
      const res = await fetch(`/api/runs/${runId}/cancel`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (data.status === 'cancelled') {
        setActiveRunId(null);
        setWsActiveNode(null);
        setNodes((nds) => nds.map((n) => ({ ...n, className: '' })));
        fetchData();
      }
    } catch (err) {
      console.error("Cancellation failed:", err);
    }
  };

  // Cancel running run from history panel
  const handleCancelRunInHistory = async (runId) => {
    try {
      const res = await fetch(`/api/runs/${runId}/cancel`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (data.status === 'cancelled') {
        fetchData();
        // Reload details for currently selected run
        handleViewRun(runId);
      }
    } catch (err) {
      console.error("Cancellation failed:", err);
    }
  };

  // Edge and node connect events inside React Flow canvas
  const onConnect = useCallback((params) => setEdges((eds) => addEdge(params, eds)), [setEdges]);

  const saveWorkflowCanvas = async () => {
    if (!selectedWorkflow) return;
    
    // Clean nodes to keep size low
    const serializedNodes = nodes.map(n => ({
      id: n.id,
      type: n.type,
      position: n.position,
      data: n.data
    }));

    const updatedWf = {
      ...selectedWorkflow,
      nodes_json: JSON.stringify(serializedNodes),
      edges_json: JSON.stringify(edges)
    };

    try {
      const res = await fetch(`/api/workflows/${selectedWorkflow.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedWf)
      });
      const data = await res.json();
      setSelectedWorkflow(data);
      fetchData();
      alert("Workflow canvas successfully saved!");
    } catch (e) {
      alert("Error saving canvas: " + e.message);
    }
  };

  // Add a new node to the canvas
  const handleAddNode = (type) => {
    let label = '';
    let data = {};
    
    if (type === 'trigger') {
      label = 'Telegram Message Trigger';
      data = { label, trigger_source: 'telegram' };
    } else if (type === 'agent') {
      if (agents.length === 0) {
        alert('Please register at least one agent in the Agent Registry first.');
        return;
      }
      const defaultAgent = agents[0];
      label = defaultAgent.name;
      data = { 
        label, 
        agent_id: defaultAgent.id, 
        role: defaultAgent.role,
        agent_role: defaultAgent.role,
        model_name: defaultAgent.model_name
      };
    } else if (type === 'condition') {
      label = 'If "success"';
      data = { label, expression: 'success' };
    } else if (type === 'triage') {
      label = 'Triage: Is travel query?';
      data = {
        label,
        triage_prompt: 'Is this related to travel?',
        model_provider: 'gemini',
        model_name: 'gemini-2.5-flash-lite'
      };
    } else if (type === 'action') {
      label = 'Send Telegram Reply';
      data = { label, action_type: 'telegram_reply' };
    }
    
    const newNode = {
      id: `${type}_${Date.now()}`,
      type: type,
      position: { x: 250 + Math.random() * 100, y: 150 + Math.random() * 100 },
      data: data
    };
    
    setNodes(prev => [...prev, newNode]);
  };

  const handleNodeDoubleClick = useCallback((event, node) => {
    const type = node.type;
    if (type === 'agent' && agents.length === 0) {
      alert('Please register at least one agent in the Agent Registry first.');
      return;
    }
    
    setEditingNode(node);
    
    const defaultAgentId = agents.length > 0 ? agents[0].id : '';
    setNodeEditForm({
      label: node.data.label || '',
      trigger_source: node.data.trigger_source || 'telegram',
      agent_id: node.data.agent_id || defaultAgentId,
      expression: node.data.expression || '',
      triage_prompt: node.data.triage_prompt || '',
      model_provider: node.data.model_provider || 'gemini',
      model_name: node.data.model_name || 'gemini-2.5-flash-lite',
      action_type: node.data.action_type || 'telegram_reply',
      archive_message: node.data.archive_message || 'we will get back to you'
    });
    
    setIsNodeEditModalOpen(true);
  }, [agents]);

  const handleSaveNodeEdit = (e) => {
    e.preventDefault();
    if (!editingNode) return;
    
    const type = editingNode.type;
    let updatedData = { ...editingNode.data };
    
    if (type === 'trigger') {
      updatedData = { 
        ...updatedData, 
        label: nodeEditForm.label || 'New Trigger', 
        trigger_source: nodeEditForm.trigger_source 
      };
      
    } else if (type === 'agent') {
      const agentId = parseInt(nodeEditForm.agent_id);
      const selectedAgent = agents.find(a => a.id === agentId);
      if (!selectedAgent) {
        alert('Invalid Agent ID.');
        return;
      }
      updatedData = { 
        ...updatedData, 
        label: selectedAgent.name, 
        agent_id: selectedAgent.id, 
        role: selectedAgent.role,
        agent_role: selectedAgent.role,
        model_name: selectedAgent.model_name
      };
      
    } else if (type === 'condition') {
      updatedData = { 
        ...updatedData, 
        label: `If "${nodeEditForm.expression}"`, 
        expression: nodeEditForm.expression 
      };
      
    } else if (type === 'triage') {
      updatedData = { 
        ...updatedData, 
        label: `Triage: ${nodeEditForm.triage_prompt}`, 
        triage_prompt: nodeEditForm.triage_prompt,
        model_provider: nodeEditForm.model_provider,
        model_name: nodeEditForm.model_name
      };
      
    } else if (type === 'action') {
      const defaultLabel = nodeEditForm.action_type === 'archive' ? 'Log & Archive Output' : 'Send Telegram Reply';
      const label = nodeEditForm.label || defaultLabel;
      updatedData = { 
        ...updatedData, 
        label, 
        action_type: nodeEditForm.action_type,
        archive_message: nodeEditForm.action_type === 'archive' ? nodeEditForm.archive_message : undefined
      };
    }
    
    setNodes((nds) => 
      nds.map((n) => {
        if (n.id === editingNode.id) {
          return {
            ...n,
            data: updatedData
          };
        }
        return n;
      })
    );
    
    setIsNodeEditModalOpen(false);
    setEditingNode(null);
  };

  // Delete workflow memory fact
  const handleDeleteMemoryKey = async (key) => {
    if (!selectedWorkflow) return;
    try {
      await fetch(`/api/workflows/${selectedWorkflow.id}/memory/${key}`, { method: 'DELETE' });
      fetchWorkflowMemory(selectedWorkflow.id);
    } catch (err) {
      console.error(err);
    }
  };

  // Agent CRUD Operations
  const handleAgentSubmit = async (e) => {
    e.preventDefault();
    const method = editingAgentId ? 'PUT' : 'POST';
    const url = editingAgentId ? `/api/agents/${editingAgentId}` : '/api/agents';

    // Align Max Turns/Rolling memory limit
    const turnsVal = parseInt(guardrailMaxTurns) || 10;
    const tokenCapVal = parseInt(guardrailTokenCap) || 180000;
    const toolTurnsVal = parseInt(guardrailMaxToolTurns) || 5;

    // Serialize guardrails states into JSON string
    const guardrailsObj = {
      max_turns: turnsVal,
      token_cap: tokenCapVal,
      max_tool_turns: toolTurnsVal,
      blocked_keywords: guardrailKeywords ? guardrailKeywords.split(',').map(k => k.trim()).filter(Boolean) : [],
      context_rules: guardrailContextRules,
      templates: guardrailTemplates
    };

    const submissionForm = {
      ...agentForm,
      memory_limit: turnsVal, // Set DB memory_limit to Max Turns for LLM compaction
      guardrails: JSON.stringify(guardrailsObj)
    };

    try {
      await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(submissionForm)
      });
      setAgentForm({ name: '', role: '', system_prompt: '', model_provider: 'gemini', model_name: 'gemini-2.5-flash', memory_limit: 10, tools: '', channels: 'telegram', guardrails: '{}' });
      setEditingAgentId(null);
      setGuardrailMaxTurns('10');
      setGuardrailTokenCap('180000');
      setGuardrailMaxToolTurns('5');
      setGuardrailKeywords('');
      setGuardrailContextRules([]);
      setGuardrailTemplates({ strict_context: false, safety_shield: false, fact_grounding: false });
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleEditAgent = (agent) => {
    setAgentForm(agent);
    setEditingAgentId(agent.id);
    
    // Parse guardrails configuration
    try {
      const parsed = JSON.parse(agent.guardrails || '{}');
      setGuardrailMaxTurns(parsed.max_turns || agent.memory_limit || '10');
      setGuardrailTokenCap(parsed.token_cap || '180000');
      setGuardrailMaxToolTurns(parsed.max_tool_turns || '5');
      setGuardrailKeywords(Array.isArray(parsed.blocked_keywords) ? parsed.blocked_keywords.join(', ') : (parsed.blocked_keywords || ''));
      setGuardrailContextRules(parsed.context_rules || []);
      setGuardrailTemplates(parsed.templates || { strict_context: false, safety_shield: false, fact_grounding: false });
    } catch (e) {
      setGuardrailMaxTurns(agent.memory_limit || '10');
      setGuardrailTokenCap('180000');
      setGuardrailMaxToolTurns('5');
      setGuardrailKeywords('');
      setGuardrailContextRules([]);
      setGuardrailTemplates({ strict_context: false, safety_shield: false, fact_grounding: false });
    }
  };

  // Context Guardrails Rules Management
  const handleAddContextRule = (e) => {
    e.preventDefault();
    if (!newRulePattern || !newRulePattern.trim()) return;
    const pattern = newRulePattern.trim();
    const response = newRuleResponse.trim() || 'Out of context';
    
    if (guardrailContextRules.some(r => r.pattern.toLowerCase() === pattern.toLowerCase())) {
      alert("A rule for this pattern already exists!");
      return;
    }
    
    setGuardrailContextRules(prev => [...prev, { pattern, response }]);
    setNewRulePattern('');
    setNewRuleResponse('');
  };

  const handleDeleteContextRule = (patternToDelete) => {
    setGuardrailContextRules(prev => prev.filter(r => r.pattern !== patternToDelete));
  };

  // Settings Form Management
  const handleSettingsSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settingsForm)
      });
      const data = await res.json();
      alert("System credentials saved successfully!" + (data.telegram_reloaded ? " Telegram bot dynamic restart triggered." : ""));
    } catch (err) {
      alert("Failed to save credentials: " + err.message);
    }
  };

  const handleDeleteAgent = async (id) => {
    if (!confirm("Are you sure you want to delete this agent?")) return;
    try {
      await fetch(`/api/agents/${id}`, { method: 'DELETE' });
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  // Workflow CRUD
  const [editingWorkflowId, setEditingWorkflowId] = useState(null);

  const handleCreateWorkflow = async (e) => {
    e.preventDefault();
    const method = editingWorkflowId ? 'PUT' : 'POST';
    const url = editingWorkflowId ? `/api/workflows/${editingWorkflowId}` : '/api/workflows';
    
    let payload;
    if (editingWorkflowId) {
      const existing = workflows.find(w => w.id === editingWorkflowId);
      payload = {
        ...existing,
        name: workflowForm.name,
        description: workflowForm.description
      };
    } else {
      // Start with a basic Trigger -> Action default structure
      const defaultNodes = [
        { id: 'n_trig', type: 'trigger', position: { x: 50, y: 150 }, data: { label: 'Telegram Input Trigger', trigger_source: 'telegram' } },
        { id: 'n_act', type: 'action', position: { x: 450, y: 150 }, data: { label: 'Send Reply Action', action_type: 'telegram_reply' } }
      ];
      const defaultEdges = [
        { id: 'e_init', source: 'n_trig', target: 'n_act' }
      ];
      payload = {
        name: workflowForm.name,
        description: workflowForm.description,
        nodes_json: JSON.stringify(defaultNodes),
        edges_json: JSON.stringify(defaultEdges),
        is_active: true
      };
    }

    try {
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      setWorkflowForm({ name: '', description: '' });
      setEditingWorkflowId(null);
      fetchData();
      if (editingWorkflowId) {
        if (selectedWorkflow && selectedWorkflow.id === editingWorkflowId) {
          setSelectedWorkflow(data);
        }
      } else {
        handleSelectWorkflow(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleEditWorkflowClick = (e, wf) => {
    e.stopPropagation();
    setEditingWorkflowId(wf.id);
    setWorkflowForm({
      name: wf.name,
      description: wf.description || ''
    });
  };

  const handleDeleteWorkflow = async (e, workflowId) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this workflow? All associated schedules will also be affected.")) return;
    try {
      await fetch(`/api/workflows/${workflowId}`, { method: 'DELETE' });
      if (selectedWorkflow && selectedWorkflow.id === workflowId) {
        setSelectedWorkflow(null);
        setNodes([]);
        setEdges([]);
      }
      setEditingWorkflowId(null);
      setWorkflowForm({ name: '', description: '' });
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  // Schedule CRUD
  const handleScheduleSubmit = async (e) => {
    e.preventDefault();
    if (!scheduleForm.workflow_id) return;
    const method = editingScheduleId ? 'PUT' : 'POST';
    const url = editingScheduleId ? `/api/schedules/${editingScheduleId}` : '/api/schedules';
    
    // Map workflow_id to integer
    const submission = {
      ...scheduleForm,
      workflow_id: parseInt(scheduleForm.workflow_id)
    };
    if (editingScheduleId) {
      submission.id = editingScheduleId;
    }

    try {
      await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(submission)
      });
      setScheduleForm({ workflow_id: '', name: '', cron_expression: '*/5 * * * *', chat_id: '' });
      setEditingScheduleId(null);
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleToggleSchedule = async (sch) => {
    try {
      const updated = {
        ...sch,
        is_active: !sch.is_active
      };
      await fetch(`/api/schedules/${sch.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      });
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleEditSchedule = (sch) => {
    setScheduleForm({
      workflow_id: sch.workflow_id.toString(),
      name: sch.name,
      cron_expression: sch.cron_expression,
      chat_id: sch.chat_id || ''
    });
    setEditingScheduleId(sch.id);
  };

  const handleDeleteSchedule = async (id) => {
    if (!confirm("Are you sure you want to delete this schedule?")) return;
    try {
      await fetch(`/api/schedules/${id}`, { method: 'DELETE' });
      if (editingScheduleId === id) {
        setEditingScheduleId(null);
        setScheduleForm({ workflow_id: '', name: '', cron_expression: '*/5 * * * *', chat_id: '' });
      }
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  // View Historical Run details
  const handleViewRun = async (runId) => {
    try {
      const res = await fetch(`/api/runs/${runId}`);
      const data = await res.json();
      setSelectedRun(data);
      if (data.run && data.run.session_id) {
        fetchSessionStats(data.run.session_id);
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="app-container">
      {/* 1. App Navigation Header */}
      <header className="app-header">
        <div className="logo-section">
          <div className="logo-icon">
            <Cpu size={20} color="#fff" />
          </div>
          <span className="logo-text">Yuno Agentic Workspace</span>
        </div>
        
        <nav className="nav-links">
          <button 
            className={`nav-tab ${activeTab === 'workflows' ? 'active' : ''}`}
            onClick={() => setActiveTab('workflows')}
          >
            <GitFork size={16} /> Workflows Canvas
          </button>
          <button 
            className={`nav-tab ${activeTab === 'agents' ? 'active' : ''}`}
            onClick={() => setActiveTab('agents')}
          >
            <Bot size={16} /> Agent Registry
          </button>
          <button 
            className={`nav-tab ${activeTab === 'runs' ? 'active' : ''}`}
            onClick={() => setActiveTab('runs')}
          >
            <History size={16} /> Run History
          </button>
          <button 
            className={`nav-tab ${activeTab === 'schedules' ? 'active' : ''}`}
            onClick={() => setActiveTab('schedules')}
          >
            <Calendar size={16} /> Cron Schedules
          </button>
          <button 
            className={`nav-tab ${activeTab === 'settings' ? 'active' : ''}`}
            onClick={() => setActiveTab('settings')}
          >
            <Settings size={16} /> Settings
          </button>
        </nav>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.8rem', color: isWsConnected ? '#34d399' : '#f43f5e' }}>
          <Activity size={14} className={isWsConnected ? 'pulse' : ''} />
          {isWsConnected ? 'Monitoring Live Stream Connected' : 'Live Stream Offline'}
        </div>
      </header>

      {/* 2. Main Worksheets Container */}
      <main className="app-workspace">
        
        {/* TAB 1: WORKFLOWS VISUAL EDITOR */}
        {activeTab === 'workflows' && (
          <>
            {/* Workflows Left Sidebar */}
            <aside className="sidebar">
              <div className="section-header">Active Workflows</div>
              <div className="item-list">
                {workflows.map(wf => (
                  <div 
                    key={wf.id} 
                    className={`glass-card ${selectedWorkflow?.id === wf.id ? 'active' : ''}`}
                    onClick={() => handleSelectWorkflow(wf)}
                    style={{ position: 'relative' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <h4 style={{ flex: 1, paddingRight: 60 }}>{wf.name}</h4>
                      <div style={{ display: 'flex', gap: 6, position: 'absolute', right: 12, top: 12 }}>
                        <button 
                          className="btn btn-secondary" 
                          style={{ padding: '3px 6px', fontSize: 10 }}
                          onClick={(e) => handleEditWorkflowClick(e, wf)}
                        >
                          Edit
                        </button>
                        <button 
                          className="btn btn-secondary" 
                          style={{ padding: '3px 6px', color: 'var(--danger)', fontSize: 10 }}
                          onClick={(e) => handleDeleteWorkflow(e, wf.id)}
                        >
                          <Trash2 size={10} />
                        </button>
                      </div>
                    </div>
                    <p style={{ marginTop: 6, fontSize: '0.8rem', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{wf.description || 'No description provided.'}</p>
                    <span className="badge badge-secondary" style={{ marginTop: 4 }}>ID: {wf.id}</span>
                  </div>
                ))}
              </div>
              
              <hr style={{ borderColor: 'var(--border)' }} />
              
              <form onSubmit={handleCreateWorkflow} className="item-list">
                <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>{editingWorkflowId ? 'Modify Custom Workflow' : 'Create Custom Workflow'}</span>
                  {editingWorkflowId && (
                    <button 
                      className="btn btn-secondary" 
                      style={{ padding: '4px 8px', fontSize: 10 }} 
                      onClick={(e) => {
                        e.preventDefault();
                        setEditingWorkflowId(null);
                        setWorkflowForm({ name: '', description: '' });
                      }}
                    >
                      Cancel
                    </button>
                  )}
                </div>
                <div className="form-group">
                  <label>Workflow Name</label>
                  <input 
                    type="text" 
                    className="form-control" 
                    value={workflowForm.name}
                    onChange={e => setWorkflowForm({...workflowForm, name: e.target.value})}
                    placeholder="e.g. Lead Triage"
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Description</label>
                  <textarea 
                    className="form-control"
                    value={workflowForm.description}
                    onChange={e => setWorkflowForm({...workflowForm, description: e.target.value})}
                    placeholder="Brief objective..."
                  />
                </div>
                <button type="submit" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }}>
                  {editingWorkflowId ? 'Save Configurations' : <><Plus size={16} /> New Workflow</>}
                </button>
              </form>
            </aside>

            {/* Split Visual Canvas + Console Workspace */}
            <div className="split-pane">
              {/* Visual Node Graph */}
              <div className="canvas-container">
                {selectedWorkflow ? (
                  <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onConnect={onConnect}
                    nodeTypes={nodeTypes}
                    onNodeDoubleClick={handleNodeDoubleClick}
                    fitView
                  >
                    <Background color="#1e293b" gap={16} size={1.5} />
                    <Controls />
                    <div className="node-palette">
                      <button className="btn btn-secondary" onClick={() => handleAddNode('trigger')}>
                        + Trigger
                      </button>
                      <button className="btn btn-secondary" onClick={() => handleAddNode('agent')}>
                        + Agent
                      </button>
                      <button className="btn btn-secondary" onClick={() => handleAddNode('condition')}>
                        + Condition
                      </button>
                      <button className="btn btn-secondary" onClick={() => handleAddNode('triage')}>
                        + Triage
                      </button>
                      <button className="btn btn-secondary" onClick={() => handleAddNode('action')}>
                        + Action
                      </button>
                    </div>
                    <div style={{ position: 'absolute', top: 15, right: 15, zIndex: 5, display: 'flex', gap: 10 }}>
                      <button className="btn btn-secondary" onClick={() => handleSelectWorkflow(selectedWorkflow)}>
                        <RefreshCw size={14} /> Revert Changes
                      </button>
                      <button className="btn btn-primary" onClick={saveWorkflowCanvas}>
                        Save Canvas Config
                      </button>
                    </div>
                  </ReactFlow>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-secondary)' }}>
                    No workflow selected. Please select one or build a new template.
                  </div>
                )}
              </div>

              {/* Real-time WebSockets Observability Dashboard */}
              <div className="monitoring-panel">
                {/* Console Log Terminal */}
                <div className="logs-console">
                  <div className="section-header" style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                    <Terminal size={14} /> Live Runtime Execution Console
                  </div>
                  
                  {wsLogs.length === 0 ? (
                    <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      Console ready. Trigger a message through Telegram or the manual controller...
                    </div>
                  ) : (
                    wsLogs.map((log, index) => {
                      let color = 'var(--text-primary)';
                      if (log.step_type === 'tool_call') color = 'var(--secondary)';
                      if (log.step_type === 'tool_response') color = 'var(--text-secondary)';
                      if (log.step_type === 'error') color = 'var(--danger)';
                      if (log.step_type === 'inter_agent_msg') color = 'var(--success)';
                      
                      return (
                        <div key={index} className="console-line" style={{ color }}>
                          <span>[{log.step_type.toUpperCase()}]: </span>
                          <span>{log.content}</span>
                        </div>
                      );
                    })
                  )}
                  <div ref={logsEndRef} />
                </div>

                {/* Observability Controller */}
                <div className="stats-pane">
                  <div className="section-header" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Activity size={14} /> Execution Observability Controller
                  </div>
                  
                  <div className="form-group">
                    <label>Test Workflow Input Message</label>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <input 
                        type="text" 
                        className="form-control" 
                        value={testInput} 
                        onChange={e => setTestInput(e.target.value)} 
                        style={{ flex: 1 }} 
                      />
                      <button className="btn btn-primary" onClick={handleRunWorkflow}>
                        <Play size={14} /> Run
                      </button>
                      <button 
                        className="btn btn-secondary" 
                        onClick={() => {
                          const newSess = `manual_${Date.now()}`;
                          setCurrentSessionId(newSess);
                          setWsStats({ promptTokens: 0, completionTokens: 0, thoughtTokens: 0, cost: 0.0 });
                          setWsLogs([]);
                          setSessionStats(null);
                        }} 
                        title="Start a new chat session"
                        style={{ padding: '0 8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                      >
                        <RefreshCw size={14} /> New
                      </button>
                    </div>
                    {activeRunId && (
                      <div style={{ marginTop: 10 }}>
                        <button 
                          className="btn" 
                          onClick={() => handleCancelWorkflow(activeRunId)}
                          style={{
                            width: '100%',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: 6,
                            background: 'rgba(239, 68, 68, 0.1)',
                            border: '1px solid rgba(239, 68, 68, 0.3)',
                            color: '#ef4444',
                            boxShadow: '0 0 10px rgba(239, 68, 68, 0.15)',
                            padding: '8px 12px',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontWeight: '500',
                            fontSize: '0.85rem',
                            transition: 'all 0.2s ease-in-out'
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'rgba(239, 68, 68, 0.25)';
                            e.currentTarget.style.border = '1px solid rgba(239, 68, 68, 0.5)';
                            e.currentTarget.style.boxShadow = '0 0 15px rgba(239, 68, 68, 0.3)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)';
                            e.currentTarget.style.border = '1px solid rgba(239, 68, 68, 0.3)';
                            e.currentTarget.style.boxShadow = '0 0 10px rgba(239, 68, 68, 0.15)';
                          }}
                        >
                          <Square size={12} fill="#ef4444" /> Cancel Active Run #{activeRunId}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        {/* TAB 2: AGENT REGISTRY */}
        {activeTab === 'agents' && (
          <div style={{ gridColumn: 'span 2', padding: 30, overflowY: 'auto', display: 'grid', gridTemplateColumns: '400px 1fr', gap: 30 }}>
            {/* Agent Registration Form */}
            <form onSubmit={handleAgentSubmit} className="glass-card" style={{ height: 'fit-content', gap: 15 }}>
              <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>{editingAgentId ? 'Modify Agent Config' : 'Register New Agent'}</span>
                {editingAgentId && (
                  <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: 10 }} onClick={() => {
                    setEditingAgentId(null);
                    setAgentForm({ name: '', role: '', system_prompt: '', model_provider: 'gemini', model_name: 'gemini-2.5-flash', memory_limit: 10, tools: '', channels: 'telegram', guardrails: '{}' });
                  }}>Cancel Edit</button>
                )}
              </div>

              <div className="form-group">
                <label>Agent Name</label>
                <input 
                  type="text" 
                  className="form-control"
                  value={agentForm.name}
                  onChange={e => setAgentForm({...agentForm, name: e.target.value})}
                  placeholder="e.g. Lead Triage Bot"
                  required
                />
              </div>

              <div className="form-group">
                <label>Role</label>
                <input 
                  type="text" 
                  className="form-control"
                  value={agentForm.role}
                  onChange={e => setAgentForm({...agentForm, role: e.target.value})}
                  placeholder="e.g. Support Specialist"
                  required
                />
              </div>

              <div className="form-group">
                <label>System Prompt (Agent Context)</label>
                <textarea 
                  className="form-control"
                  rows={4}
                  value={agentForm.system_prompt}
                  onChange={e => setAgentForm({...agentForm, system_prompt: e.target.value})}
                  placeholder="Tell the agent how it should behave..."
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 15 }}>
                <div className="form-group">
                  <label style={{ fontWeight: 'bold' }}>Model Provider</label>
                  <select 
                    className="form-control"
                    value={agentForm.model_provider}
                    onChange={e => {
                      const newProvider = e.target.value;
                      const defaultModel = modelsByProvider[newProvider]?.[0] || '';
                      setAgentForm({
                        ...agentForm,
                        model_provider: newProvider,
                        model_name: defaultModel
                      });
                    }}
                  >
                    <option value="gemini">Gemini</option>
                    <option value="openai">OpenAI</option>
                  </select>
                </div>

                <div className="form-group">
                  <label style={{ fontWeight: 'bold' }}>Model Name</label>
                  <select 
                    className="form-control"
                    value={agentForm.model_name}
                    onChange={e => setAgentForm({...agentForm, model_name: e.target.value})}
                  >
                    {(modelsByProvider[agentForm.model_provider] || []).map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label style={{ fontWeight: 'bold' }}>Enabled Tools</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                  {availableTools.map(tool => {
                    const isSelected = agentForm.tools.split(',')
                      .map(t => t.trim())
                      .includes(tool.id);
                    return (
                      <button
                        key={tool.id}
                        type="button"
                        className={`badge ${isSelected ? 'badge-primary' : 'badge-secondary'}`}
                        style={{ cursor: 'pointer', border: '1px solid var(--border)', padding: '6px 10px', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center' }}
                        onClick={() => {
                          let currentTools = agentForm.tools.split(',').map(t => t.trim()).filter(Boolean);
                          if (currentTools.includes(tool.id)) {
                            currentTools = currentTools.filter(t => t !== tool.id);
                          } else {
                            currentTools.push(tool.id);
                          }
                          setAgentForm({ ...agentForm, tools: currentTools.join(', ') });
                        }}
                      >
                        {tool.name} {isSelected ? '✓' : '+'}
                      </button>
                    );
                  })}
                </div>
                
                {/* Tool descriptions block */}
                <div style={{ marginTop: 8, fontSize: '0.75rem', color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.02)', padding: 10, borderRadius: 6, border: '1px solid var(--border)' }}>
                  <strong style={{ color: 'var(--primary)' }}>Tool Guides:</strong>
                  <ul style={{ margin: '4px 0 0 16px', padding: 0, listStyleType: 'disc' }}>
                    {Object.entries(toolInfo).map(([id, desc]) => (
                      <li key={id} style={{ marginBottom: 2 }}>
                        <span style={{ color: 'var(--text-primary)', fontWeight: 'bold' }}>{id}:</span> {desc}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <details className="glass-card" style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 8, background: 'rgba(255, 255, 255, 0.01)', cursor: 'pointer' }}>
                <summary style={{ fontWeight: 'bold', fontSize: '0.85rem', color: 'var(--primary)', userSelect: 'none' }}>
                  Advanced Controls & Execution Limits
                </summary>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 15, marginTop: 12, cursor: 'default' }} onClick={e => e.stopPropagation()}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 15 }}>
                    <div className="form-group">
                      <label style={{ fontWeight: 'bold' }}>Max Turns (Compaction)</label>
                      <input 
                        type="number" 
                        className="form-control"
                        value={guardrailMaxTurns}
                        onChange={e => setGuardrailMaxTurns(e.target.value)}
                        placeholder="e.g. 10"
                      />
                      <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Default: 10 turns.</span>
                    </div>

                    <div className="form-group">
                      <label style={{ fontWeight: 'bold' }}>Token Cap Limit</label>
                      <input 
                        type="number" 
                        className="form-control"
                        value={guardrailTokenCap}
                        onChange={e => setGuardrailTokenCap(e.target.value)}
                        placeholder="e.g. 180000"
                      />
                      <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Default: 180,000 tokens.</span>
                    </div>

                    <div className="form-group">
                      <label style={{ fontWeight: 'bold' }}>Max Tool Turns</label>
                      <input 
                        type="number" 
                        className="form-control"
                        value={guardrailMaxToolTurns}
                        onChange={e => setGuardrailMaxToolTurns(e.target.value)}
                        placeholder="e.g. 5"
                      />
                      <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Default: 5 turns.</span>
                    </div>
                  </div>
                  
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', background: 'rgba(99, 102, 241, 0.05)', padding: 10, borderRadius: 6, border: '1px solid var(--border)' }}>
                    ℹ️ <strong>How limits trigger history compaction:</strong> Memory compaction (summarizing old messages) is automatically triggered when the conversation exceeds <strong>Max Turns</strong> or hits the <strong>Token Cap Limit</strong>, whichever occurs first. This keeps the prompt short and saves API costs.
                  </div>
                </div>
              </details>

              <div className="form-group">
                <label style={{ fontWeight: 'bold' }}>Safety Keyword Filters (Comma separated)</label>
                <input 
                  type="text" 
                  className="form-control"
                  value={guardrailKeywords}
                  onChange={e => setGuardrailKeywords(e.target.value)}
                  placeholder="e.g. password, credit card, spam"
                />
                <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                  Blocks and warns if user inputs contain any of these keywords (input filter).
                </span>
              </div>

              <div className="form-group" style={{ display: 'flex', flexDirection: 'column', gap: 10, border: '1px solid var(--border)', padding: 12, borderRadius: 8 }}>
                <label style={{ fontWeight: 'bold', fontSize: '0.8rem', color: 'var(--primary)' }}>Semantic Guardrail Templates</label>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                  Toggle LLM prompt-level safety overlays to enforce dynamic topic alignment and security natively:
                </span>
                
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.78rem', cursor: 'pointer', userSelect: 'none' }}>
                  <input 
                    type="checkbox"
                    checked={guardrailTemplates.strict_context}
                    onChange={e => setGuardrailTemplates({ ...guardrailTemplates, strict_context: e.target.checked })}
                  />
                  <div>
                    <strong>Strict Role Adherence</strong><br />
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Refuses queries going out-of-context wrt role (e.g. travel agent refusing recipes/groceries).</span>
                  </div>
                </label>

                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.78rem', cursor: 'pointer', userSelect: 'none' }}>
                  <input 
                    type="checkbox"
                    checked={guardrailTemplates.safety_shield}
                    onChange={e => setGuardrailTemplates({ ...guardrailTemplates, safety_shield: e.target.checked })}
                  />
                  <div>
                    <strong>Prompt Injection Shield</strong><br />
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Blocks instructions hacks (e.g. "ignore previous instructions") or revealing system instructions.</span>
                  </div>
                </label>

                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.78rem', cursor: 'pointer', userSelect: 'none' }}>
                  <input 
                    type="checkbox"
                    checked={guardrailTemplates.fact_grounding}
                    onChange={e => setGuardrailTemplates({ ...guardrailTemplates, fact_grounding: e.target.checked })}
                  />
                  <div>
                    <strong>Fact Grounding Enforcer</strong><br />
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Minimizes hallucinations by strictly enforcing answers using retrieved tool context only.</span>
                  </div>
                </label>
              </div>

              <button type="submit" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }}>
                {editingAgentId ? 'Save Configurations' : 'Register Agent'}
              </button>
            </form>

            {/* Grid of registered agents */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 20, height: 'fit-content' }}>
              {agents.map(agent => (
                <div key={agent.id} className="glass-card" style={{ cursor: 'default' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <h4 style={{ color: 'var(--primary)' }}>{agent.name}</h4>
                      <span className="badge badge-secondary" style={{ marginTop: 4 }}>{agent.role}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button className="btn btn-secondary" style={{ padding: '5px 8px' }} onClick={() => handleEditAgent(agent)}>
                        Edit
                      </button>
                      <button className="btn btn-secondary" style={{ padding: '5px 8px', color: 'var(--danger)' }} onClick={() => handleDeleteAgent(agent.id)}>
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>

                  <p style={{ fontSize: '0.82rem', marginTop: 10, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {agent.system_prompt}
                  </p>

                  <hr style={{ borderColor: 'var(--border)', margin: '10px 0' }} />

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, fontSize: '0.72rem' }}>
                    <span className="badge badge-primary">{agent.model_provider}: {agent.model_name}</span>
                    {agent.tools ? (
                      agent.tools.split(',').map(t => (
                        <span key={t} className="badge badge-secondary">Tool: {t.strip ? t.strip() : t.trim()}</span>
                      ))
                    ) : (
                      <span className="badge badge-secondary" style={{ fontStyle: 'italic', opacity: 0.6 }}>No tools</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 3: RUNS HISTORY */}
        {activeTab === 'runs' && (
          <div style={{ gridColumn: 'span 2', padding: 30, overflowY: 'auto', display: 'grid', gridTemplateColumns: '1fr 450px', gap: 30 }}>
            {/* Table of execution histories */}
            <div className="glass-card" style={{ height: 'fit-content', padding: 20 }}>
              <div className="section-header" style={{ marginBottom: 15 }}>Workflow Execution History</div>
              
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)' }}>
                    <th style={{ padding: 12 }}>Run ID</th>
                    <th style={{ padding: 12 }}>Workflow</th>
                    <th style={{ padding: 12 }}>Started At</th>
                    <th style={{ padding: 12 }}>Trigger Source</th>
                    <th style={{ padding: 12 }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.slice((runsPage - 1) * 25, runsPage * 25).map(run => {
                    const matchedWf = workflows.find(w => w.id === run.workflow_id);
                    return (
                      <tr 
                        key={run.id} 
                        style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer', pointerEvents: 'auto', background: selectedRun?.run.id === run.id ? 'hsla(263, 84%, 62%, 0.05)' : '' }}
                        className="table-row-hover"
                        onClick={() => handleViewRun(run.id)}
                      >
                        <td onClick={() => handleViewRun(run.id)} style={{ padding: 12, fontWeight: 'bold', pointerEvents: 'auto' }}>#{run.id}</td>
                        <td onClick={() => handleViewRun(run.id)} style={{ padding: 12, pointerEvents: 'auto' }}>{matchedWf?.name || `Workflow #${run.workflow_id}`}</td>
                        <td onClick={() => handleViewRun(run.id)} style={{ padding: 12, pointerEvents: 'auto' }}>{new Date(run.started_at).toLocaleString()}</td>
                        <td onClick={() => handleViewRun(run.id)} style={{ padding: 12, pointerEvents: 'auto' }}>
                          <span className="badge badge-secondary">{run.trigger_source}</span>
                        </td>
                        <td onClick={() => handleViewRun(run.id)} style={{ padding: 12, pointerEvents: 'auto' }}>
                          {run.status === 'completed' ? (
                            <span style={{ color: 'var(--success)', display: 'flex', alignItems: 'center', gap: 4 }}>
                              <CheckCircle size={14} /> Completed
                            </span>
                          ) : run.status === 'failed' ? (
                            <span style={{ color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: 4 }}>
                              <XCircle size={14} /> Failed
                            </span>
                          ) : (
                            <span style={{ color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: 4 }}>
                              <Activity size={14} className="pulse" /> Active
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {/* Pagination Controls */}
              {(() => {
                const totalPages = Math.ceil(runs.length / 25) || 1;
                if (totalPages <= 1) return null;
                return (
                  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 6, marginTop: 20 }}>
                    <button 
                      className="btn btn-secondary" 
                      style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                      onClick={() => setRunsPage(prev => Math.max(prev - 1, 1))}
                      disabled={runsPage === 1}
                    >
                      Prev
                    </button>
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
                      <button
                        key={p}
                        className={`btn ${runsPage === p ? 'btn-primary' : 'btn-secondary'}`}
                        style={{ padding: '4px 8px', fontSize: '0.75rem', minWidth: 28 }}
                        onClick={() => setRunsPage(p)}
                      >
                        {p}
                      </button>
                    ))}
                    <button 
                      className="btn btn-secondary" 
                      style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                      onClick={() => setRunsPage(prev => Math.min(prev + 1, totalPages))}
                      disabled={runsPage === totalPages}
                    >
                      Next
                    </button>
                  </div>
                );
              })()}
            </div>

            {/* Static run log inspection pane */}
            <div className="glass-card" style={{ height: 'fit-content' }}>
              <div className="section-header" style={{ marginBottom: 15 }}>Run Details & Log History</div>
              
              {selectedRun ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 15 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 15, fontSize: '0.82rem' }}>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Trigger Source:</span><br />
                      <b>{selectedRun.run.trigger_source}</b>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Status:</span><br />
                      <b>{selectedRun.run.status}</b>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Started:</span><br />
                      <b>{new Date(selectedRun.run.started_at).toLocaleString()}</b>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Completed:</span><br />
                      <b>{selectedRun.run.completed_at ? new Date(selectedRun.run.completed_at).toLocaleString() : 'N/A'}</b>
                    </div>
                    {selectedRun.run.status === 'running' && (
                      <div style={{ gridColumn: 'span 2', marginTop: 5 }}>
                        <button 
                          className="btn" 
                          onClick={() => handleCancelRunInHistory(selectedRun.run.id)}
                          style={{
                            width: '100%',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: 6,
                            background: 'rgba(239, 68, 68, 0.1)',
                            border: '1px solid rgba(239, 68, 68, 0.3)',
                            color: '#ef4444',
                            boxShadow: '0 0 10px rgba(239, 68, 68, 0.15)',
                            padding: '8px 12px',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontWeight: '500',
                            fontSize: '0.82rem',
                            transition: 'all 0.2s ease-in-out'
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'rgba(239, 68, 68, 0.25)';
                            e.currentTarget.style.border = '1px solid rgba(239, 68, 68, 0.5)';
                            e.currentTarget.style.boxShadow = '0 0 15px rgba(239, 68, 68, 0.3)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)';
                            e.currentTarget.style.border = '1px solid rgba(239, 68, 68, 0.3)';
                            e.currentTarget.style.boxShadow = '0 0 10px rgba(239, 68, 68, 0.15)';
                          }}
                        >
                          <Square size={12} fill="#ef4444" /> Cancel Execution Run
                        </button>
                      </div>
                    )}
                  </div>

                  {(() => {
                    const runPromptTokens = selectedRun.logs?.reduce((sum, log) => sum + (log.prompt_tokens || 0), 0) || 0;
                    const runCompletionTokens = selectedRun.logs?.reduce((sum, log) => sum + (log.completion_tokens || 0), 0) || 0;
                    const runThoughtTokens = selectedRun.logs?.reduce((sum, log) => sum + (log.thought_tokens || 0), 0) || 0;
                    const runCost = selectedRun.logs?.reduce((sum, log) => sum + (log.usd_cost || 0.0), 0) || 0;
                    const runTotalTokens = runPromptTokens + runCompletionTokens + runThoughtTokens;

                    return (
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 15, marginTop: 10 }}>
                        {/* 1. Selected Run Stats */}
                        <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: 12, borderRadius: 8, border: '1px solid var(--border)' }}>
                          <div style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--primary)', marginBottom: 8 }}>
                            This Run's Stats
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.78rem' }}>
                            <div>
                              <span style={{ color: 'var(--text-muted)' }}>Cost of this run:</span>{' '}
                              <b style={{ color: 'var(--primary)' }}>${runCost.toFixed(5)}</b>
                            </div>
                            <div>
                              <span style={{ color: 'var(--text-muted)' }}>Tokens:</span>{' '}
                              <b>{runTotalTokens.toLocaleString()}</b> <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>({runPromptTokens}p / {runCompletionTokens}c / {runThoughtTokens}t)</span>
                            </div>
                          </div>
                        </div>

                        {/* 2. Session Accumulated Stats */}
                        {sessionStats && selectedRun.run.session_id === sessionStats.session_id && (
                          <div style={{ background: 'rgba(99, 102, 241, 0.05)', padding: 12, borderRadius: 8, border: '1px solid var(--border)' }}>
                            <div style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--success)', marginBottom: 8, display: 'flex', justifyContent: 'space-between' }}>
                              <span>Session Totals</span>
                              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>ID: {selectedRun.run.session_id.substring(0, 8)}...</span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.78rem' }}>
                              <div>
                                <span style={{ color: 'var(--text-muted)' }}>Accumulated Cost:</span>{' '}
                                <b style={{ color: 'var(--success)' }}>${sessionStats.total_cost.toFixed(5)}</b>
                              </div>
                              <div>
                                <span style={{ color: 'var(--text-muted)' }}>Total Turns:</span>{' '}
                                <b>{sessionStats.total_turns}</b>
                              </div>
                              <div>
                                <span style={{ color: 'var(--text-muted)' }}>Accumulated Tokens:</span>{' '}
                                <b>{(sessionStats.total_prompt_tokens + sessionStats.total_completion_tokens + (sessionStats.total_thought_tokens || 0)).toLocaleString()}</b>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()}

                  <hr style={{ borderColor: 'var(--border)' }} />
                  
                  <div className="section-header">Execution Trace Logs</div>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 400, overflowY: 'auto', fontFamily: 'monospace', fontSize: '0.8rem', background: '#020617', padding: 15, borderRadius: 8 }}>
                    {selectedRun.logs.map((log, index) => (
                      <div key={index} style={{ borderBottom: '1px solid #1e293b', paddingBottom: 6 }}>
                        <div style={{ fontSize: '0.7rem', color: '#64748b', display: 'flex', justifyContent: 'space-between' }}>
                          <span>[{log.step_type.toUpperCase()}]</span>
                          {log.usd_cost > 0 && <span style={{ color: '#38bdf8' }}>${log.usd_cost.toFixed(5)}</span>}
                        </div>
                        <div style={{ marginTop: 2, wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
                          {log.message_from && <span style={{ color: '#a78bfa', fontWeight: 'bold' }}>{log.message_from}: </span>}
                          {log.content}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ color: 'var(--text-muted)', fontStyle: 'italic', padding: 20, textAlign: 'center' }}>
                  Click an execution run on the left to view logs.
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 4: CRON SCHEDULES */}
        {activeTab === 'schedules' && (
          <div style={{ gridColumn: 'span 2', padding: 30, overflowY: 'auto', display: 'grid', gridTemplateColumns: '400px 1fr', gap: 30 }}>
            {/* Create Schedule Form */}
            <form onSubmit={handleScheduleSubmit} className="glass-card" style={{ height: 'fit-content', gap: 15 }}>
              <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>{editingScheduleId ? `Modify Schedule #${editingScheduleId}` : 'Schedule Agent Workflow'}</span>
                {editingScheduleId && (
                  <button 
                    type="button" 
                    className="btn btn-secondary" 
                    style={{ padding: '4px 8px', fontSize: 10 }} 
                    onClick={() => {
                      setEditingScheduleId(null);
                      setScheduleForm({ workflow_id: '', name: '', cron_expression: '*/5 * * * *', chat_id: '' });
                    }}
                  >
                    Cancel Edit
                  </button>
                )}
              </div>
              
              <div className="form-group">
                <label>Select Target Workflow</label>
                <select 
                  className="form-control"
                  value={scheduleForm.workflow_id}
                  onChange={e => setScheduleForm({...scheduleForm, workflow_id: e.target.value})}
                  required
                >
                  <option value="">-- Choose Workflow --</option>
                  {workflows.map(wf => (
                    <option key={wf.id} value={wf.id}>{wf.name} (ID: {wf.id})</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Schedule Identifier Name</label>
                <input 
                  type="text" 
                  className="form-control"
                  value={scheduleForm.name}
                  onChange={e => setScheduleForm({...scheduleForm, name: e.target.value})}
                  placeholder="e.g. Daily Research Trigger"
                  required
                />
              </div>

              <div className="form-group">
                <label>Cron Expression</label>
                <input 
                  type="text" 
                  className="form-control"
                  value={scheduleForm.cron_expression}
                  onChange={e => setScheduleForm({...scheduleForm, cron_expression: e.target.value})}
                  placeholder="e.g., */5 * * * * (every 5 minutes)"
                  required
                />
                <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Format: minute hour day_of_month month day_of_week &nbsp;·&nbsp; <strong>Runs in system's local timezone</strong> (works according to the local timezone automatically, no UTC conversion required)</span>
              </div>

              <div className="form-group">
                <label>Telegram Chat ID</label>
                <input
                  type="text"
                  className="form-control"
                  value={scheduleForm.chat_id}
                  onChange={e => setScheduleForm({...scheduleForm, chat_id: e.target.value})}
                  placeholder="Send /start to the bot to get your Chat ID"
                />
                <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Where scheduled output is delivered. Leave blank to run silently (logs only).</span>
              </div>

              <button type="submit" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }}>
                {editingScheduleId ? 'Save Schedule Configurations' : <><Plus size={16} /> Register Scheduled Trigger</>}
              </button>
            </form>

            {/* List of active schedules */}
            <div className="glass-card" style={{ height: 'fit-content', padding: 20 }}>
              <div className="section-header" style={{ marginBottom: 15 }}>Active Automation Schedules</div>
              
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)' }}>
                    <th style={{ padding: 12 }}>Schedule Name</th>
                    <th style={{ padding: 12 }}>Workflow</th>
                    <th style={{ padding: 12 }}>Cron Expression</th>
                    <th style={{ padding: 12 }}>Status</th>
                    <th style={{ padding: 12, textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {schedules.map(sch => {
                    const matchedWf = workflows.find(w => w.id === sch.workflow_id);
                    return (
                      <tr key={sch.id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: 12, fontWeight: 'bold' }}>{sch.name}</td>
                        <td style={{ padding: 12 }}>{matchedWf?.name || `Workflow #${sch.workflow_id}`}</td>
                        <td style={{ padding: 12 }}><code>{sch.cron_expression}</code></td>
                        <td style={{ padding: 12 }}>
                          <span className={`badge ${sch.is_active ? 'badge-success' : 'badge-warning'}`}>
                            {sch.is_active ? 'Active' : 'Paused'}
                          </span>
                        </td>
                        <td style={{ padding: 12, textAlign: 'right' }}>
                          <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', alignItems: 'center' }}>
                            <button 
                              type="button"
                              className="btn btn-secondary" 
                              style={{ 
                                padding: '6px 10px', 
                                display: 'flex', 
                                alignItems: 'center', 
                                gap: 4,
                                borderColor: sch.is_active ? 'var(--warning)' : 'var(--success)',
                                color: sch.is_active ? 'var(--warning)' : 'var(--success)'
                              }}
                              onClick={() => handleToggleSchedule(sch)}
                              title={sch.is_active ? "Pause schedule job" : "Start schedule job"}
                            >
                              {sch.is_active ? <Pause size={12} /> : <Play size={12} />}
                              {sch.is_active ? 'Pause' : 'Start'}
                            </button>
                            <button 
                              type="button"
                              className="btn btn-secondary" 
                              style={{ padding: '6px 10px' }}
                              onClick={() => handleEditSchedule(sch)}
                            >
                              Edit
                            </button>
                            <button 
                              type="button"
                              className="btn btn-secondary" 
                              style={{ padding: '6px 10px', color: 'var(--danger)', borderColor: 'var(--border)' }}
                              onClick={() => handleDeleteSchedule(sch.id)}
                            >
                              <Trash2 size={12} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {schedules.length === 0 && (
                    <tr>
                      <td colSpan={5} style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        No automation schedules configured. Set one on the left to run workflows in background!
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 5: SYSTEM CREDENTIALS SETTINGS */}
        {activeTab === 'settings' && (
          <div style={{ gridColumn: 'span 2', padding: 30, overflowY: 'auto', display: 'flex', justifyContent: 'center' }}>
            <form onSubmit={handleSettingsSubmit} className="glass-card" style={{ width: '600px', height: 'fit-content', gap: 20, padding: 30 }}>
              <div className="section-header" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '1.2rem', color: 'var(--primary)' }}>
                <Settings size={20} /> System Credentials & Bot Configurations
              </div>
              
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                Configure API keys and messaging channel tokens dynamically. Changes to the Telegram Bot Token will trigger a safe runtime reload of the bot polling process.
              </p>
              
              <div className="form-group">
                <label style={{ fontWeight: 'bold' }}>Telegram Bot Token</label>
                <input 
                  type="password" 
                  className="form-control"
                  value={settingsForm.TELEGRAM_BOT_TOKEN}
                  onChange={e => setSettingsForm({...settingsForm, TELEGRAM_BOT_TOKEN: e.target.value})}
                  placeholder="e.g. 1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ"
                />
                <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Used as the primary conversation gateway. Reloads dynamically on save.</span>
              </div>

              <div className="form-group">
                <label style={{ fontWeight: 'bold' }}>Gemini API Key</label>
                <input 
                  type="password" 
                  className="form-control"
                  value={settingsForm.GEMINI_API_KEY}
                  onChange={e => setSettingsForm({...settingsForm, GEMINI_API_KEY: e.target.value})}
                  placeholder="e.g. AIzaSy..."
                />
                <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Required for Gemini LLM models.</span>
              </div>

              <div className="form-group">
                <label style={{ fontWeight: 'bold' }}>OpenAI API Key</label>
                <input 
                  type="password" 
                  className="form-control"
                  value={settingsForm.OPENAI_API_KEY}
                  onChange={e => setSettingsForm({...settingsForm, OPENAI_API_KEY: e.target.value})}
                  placeholder="e.g. sk-proj-..."
                />
                <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Required for OpenAI LLM models.</span>
              </div>
              
              <div className="form-group">
                <label style={{ fontWeight: 'bold', opacity: 0.6 }}>Slack Bot Token (Optional)</label>
                <input 
                  type="password" 
                  className="form-control"
                  value={settingsForm.SLACK_BOT_TOKEN}
                  onChange={e => setSettingsForm({...settingsForm, SLACK_BOT_TOKEN: e.target.value})}
                  placeholder="e.g. xoxb-your-slack-bot-token"
                />
              </div>

              <div style={{ border: '1px solid var(--border)', padding: 15, borderRadius: 8, display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{ fontWeight: 'bold', fontSize: '0.88rem', opacity: 0.6 }}>WhatsApp Cloud API Settings (Optional)</div>
                
                <div className="form-group">
                  <label style={{ fontSize: '0.78rem' }}>WhatsApp Access Token</label>
                  <input 
                    type="password" 
                    className="form-control"
                    value={settingsForm.WHATSAPP_ACCESS_TOKEN}
                    onChange={e => setSettingsForm({...settingsForm, WHATSAPP_ACCESS_TOKEN: e.target.value})}
                    placeholder="Temporary or Permanent System User Access Token"
                  />
                </div>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 15 }}>
                  <div className="form-group">
                    <label style={{ fontSize: '0.78rem' }}>Phone Number ID</label>
                    <input 
                      type="text" 
                      className="form-control"
                      value={settingsForm.WHATSAPP_PHONE_NUMBER_ID}
                      onChange={e => setSettingsForm({...settingsForm, WHATSAPP_PHONE_NUMBER_ID: e.target.value})}
                      placeholder="e.g. 10987654321"
                    />
                  </div>
                  
                  <div className="form-group">
                    <label style={{ fontSize: '0.78rem' }}>Verify Token (Webhook)</label>
                    <input 
                      type="password" 
                      className="form-control"
                      value={settingsForm.WHATSAPP_VERIFY_TOKEN}
                      onChange={e => setSettingsForm({...settingsForm, WHATSAPP_VERIFY_TOKEN: e.target.value})}
                      placeholder="e.g. verify_me"
                    />
                  </div>
                </div>
              </div>

              <button type="submit" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', padding: '12px 0', fontSize: '0.95rem' }}>
                Save & Apply Credentials
              </button>
            </form>
          </div>
        )}

      </main>

      {/* Node Editing Modal */}
      {isNodeEditModalOpen && editingNode && (
        <div className="custom-modal-overlay" onClick={() => {
          setIsNodeEditModalOpen(false);
          setEditingNode(null);
        }}>
          <div className="custom-modal-card" onClick={e => e.stopPropagation()}>
            <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
              <span>Configure {editingNode.type.charAt(0).toUpperCase() + editingNode.type.slice(1)} Node</span>
              <button 
                className="btn btn-secondary" 
                style={{ padding: '4px 8px', fontSize: 11 }} 
                onClick={() => {
                  setIsNodeEditModalOpen(false);
                  setEditingNode(null);
                }}
              >
                Cancel
              </button>
            </div>
            
            <form onSubmit={handleSaveNodeEdit} style={{ display: 'flex', flexDirection: 'column', gap: 15 }}>
              
              {/* Trigger Node Form Fields */}
              {editingNode.type === 'trigger' && (
                <>
                  <div className="form-group">
                    <label>Node Label</label>
                    <input 
                      type="text" 
                      className="form-control"
                      value={nodeEditForm.label}
                      onChange={e => setNodeEditForm({...nodeEditForm, label: e.target.value})}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>Trigger Source</label>
                    <select 
                      className="form-control"
                      value={nodeEditForm.trigger_source}
                      onChange={e => setNodeEditForm({...nodeEditForm, trigger_source: e.target.value})}
                    >
                      <option value="telegram">Telegram</option>
                      <option value="slack">Slack</option>
                      <option value="whatsapp">WhatsApp</option>
                      <option value="schedule">Schedule</option>
                      <option value="manual">Manual</option>
                    </select>
                  </div>
                </>
              )}

              {/* Agent Node Form Fields */}
              {editingNode.type === 'agent' && (
                <div className="form-group">
                  <label>Select Agent</label>
                  <select 
                    className="form-control"
                    value={nodeEditForm.agent_id}
                    onChange={e => setNodeEditForm({...nodeEditForm, agent_id: e.target.value})}
                    required
                  >
                    {agents.map(a => (
                      <option key={a.id} value={a.id}>
                        {a.id}: {a.name} ({a.role})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Condition Node Form Fields */}
              {editingNode.type === 'condition' && (
                <div className="form-group">
                  <label>Condition Expression (Keyword check in output)</label>
                  <input 
                    type="text" 
                    className="form-control"
                    placeholder="e.g. approve, error, yes"
                    value={nodeEditForm.expression}
                    onChange={e => setNodeEditForm({...nodeEditForm, expression: e.target.value})}
                    required
                  />
                </div>
              )}

              {/* Triage Node Form Fields */}
              {editingNode.type === 'triage' && (
                <>
                  <div className="form-group">
                    <label>Semantic Check Question</label>
                    <textarea 
                      className="form-control"
                      rows={3}
                      placeholder="e.g. Is the user requesting a custom vacation booking schedule?"
                      value={nodeEditForm.triage_prompt}
                      onChange={e => setNodeEditForm({...nodeEditForm, triage_prompt: e.target.value})}
                      required
                    />
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 15 }}>
                    <div className="form-group">
                      <label>Model Provider</label>
                      <select 
                        className="form-control"
                        value={nodeEditForm.model_provider}
                        onChange={e => {
                          const provider = e.target.value;
                          const defaultModel = modelsByProvider[provider]?.[0] || '';
                          setNodeEditForm({
                            ...nodeEditForm,
                            model_provider: provider,
                            model_name: defaultModel
                          });
                        }}
                      >
                        <option value="gemini">Gemini</option>
                        <option value="openai">OpenAI</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Model Name</label>
                      <select 
                        className="form-control"
                        value={nodeEditForm.model_name}
                        onChange={e => setNodeEditForm({...nodeEditForm, model_name: e.target.value})}
                      >
                        {(modelsByProvider[nodeEditForm.model_provider] || []).map(m => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </>
              )}

              {/* Action Node Form Fields */}
              {editingNode.type === 'action' && (
                <>
                  <div className="form-group">
                    <label>Node Label</label>
                    <input 
                      type="text" 
                      className="form-control"
                      placeholder="e.g. Send Success Notification"
                      value={nodeEditForm.label}
                      onChange={e => setNodeEditForm({...nodeEditForm, label: e.target.value})}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>Action Type</label>
                    <select 
                      className="form-control"
                      value={nodeEditForm.action_type}
                      onChange={e => setNodeEditForm({...nodeEditForm, action_type: e.target.value})}
                    >
                      <option value="telegram_reply">Telegram Reply</option>
                      <option value="archive">Archive Output</option>
                    </select>
                  </div>
                  
                  {nodeEditForm.action_type === 'archive' && (
                    <div className="form-group">
                      <label>Archive Reply Message (Sent over Telegram)</label>
                      <input 
                        type="text" 
                        className="form-control"
                        placeholder="e.g. we will get back to you"
                        value={nodeEditForm.archive_message}
                        onChange={e => setNodeEditForm({...nodeEditForm, archive_message: e.target.value})}
                        required
                      />
                    </div>
                  )}
                </>
              )}

              <button 
                type="submit" 
                className="btn btn-primary" 
                style={{ width: '100%', justifyContent: 'center', marginTop: 10, padding: 12 }}
              >
                Save Changes
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
