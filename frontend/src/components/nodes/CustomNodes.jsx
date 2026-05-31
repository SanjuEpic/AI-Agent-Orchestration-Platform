import React from 'react';
import { Handle, Position } from '@xyflow/react';

export const TriggerNode = ({ data, className }) => {
  return (
    <div className={`custom-node node-trigger ${className || ''}`}>
      <div className="node-title">
        <span>Trigger</span>
        <span className="badge badge-secondary">{data.trigger_source || 'system'}</span>
      </div>
      <div className="node-label">{data.label || 'Message In'}</div>
      <Handle type="source" position={Position.Right} id="a" style={{ background: '#38bdf8', width: 8, height: 8 }} />
    </div>
  );
};

export const AgentNode = ({ data, className }) => {
  return (
    <div className={`custom-node node-agent ${className || ''}`}>
      <div className="node-title">
        <span>Agent Node</span>
        {(data.agent_role || data.role) && <span className="badge badge-primary">{data.agent_role || data.role}</span>}
      </div>
      <div className="node-label">{data.label || 'AI Assistant'}</div>
      {data.model_name && <div className="node-subtext">{data.model_name}</div>}
      <Handle type="target" position={Position.Left} id="in" style={{ background: '#818cf8', width: 8, height: 8 }} />
      <Handle type="source" position={Position.Right} id="out" style={{ background: '#818cf8', width: 8, height: 8 }} />
    </div>
  );
};

export const ConditionNode = ({ data, className }) => {
  return (
    <div className={`custom-node node-condition ${className || ''}`} style={{ minHeight: 90 }}>
      <div className="node-title">
        <span>Router / If</span>
      </div>
      <div className="node-label" style={{ fontSize: 11 }}>Matches: <b>"{data.expression}"</b></div>
      
      {/* Target input connection */}
      <Handle type="target" position={Position.Left} id="in" style={{ background: '#fb7185', width: 8, height: 8 }} />
      
      {/* Branched outputs (True upper Right, False lower Right) */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', marginTop: 10, gap: 8, fontSize: 10, fontWeight: 'bold' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span>True</span>
          <Handle 
            type="source" 
            position={Position.Right} 
            id="true" 
            style={{ top: '60%', background: '#34d399', width: 8, height: 8 }} 
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span>False</span>
          <Handle 
            type="source" 
            position={Position.Right} 
            id="false" 
            style={{ top: '82%', background: '#f43f5e', width: 8, height: 8 }} 
          />
        </div>
      </div>
    </div>
  );
};

export const ActionNode = ({ data, className }) => {
  return (
    <div className={`custom-node node-action ${className || ''}`}>
      <div className="node-title">
        <span>Action Output</span>
        <span className="badge badge-success">{data.action_type || 'dispatch'}</span>
      </div>
      <div className="node-label">{data.label || 'Send Message'}</div>
      <Handle type="target" position={Position.Left} id="in" style={{ background: '#34d399', width: 8, height: 8 }} />
    </div>
  );
};

export const TriageNode = ({ data, className }) => {
  return (
    <div className={`custom-node node-triage ${className || ''}`} style={{ minHeight: 110 }}>
      <div className="node-title">
        <span>Triage / Semantic Guard</span>
        {data.model_provider && <span className="badge badge-secondary">{data.model_provider}</span>}
      </div>
      <div className="node-label" style={{ fontSize: 11 }}>Verify: <b>"{data.triage_prompt}"</b></div>
      {data.model_name && <div className="node-subtext" style={{ fontSize: 9, marginTop: 4 }}>Model: {data.model_name}</div>}
      
      {/* Target input handle */}
      <Handle type="target" position={Position.Left} id="in" style={{ background: '#f59e0b', width: 8, height: 8 }} />
      
      {/* Output branch handles (True/False) */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', marginTop: 10, gap: 8, fontSize: 10, fontWeight: 'bold' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span>Pass (True)</span>
          <Handle 
            type="source" 
            position={Position.Right} 
            id="true" 
            style={{ top: '65%', background: '#34d399', width: 8, height: 8 }} 
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span>Fail (False)</span>
          <Handle 
            type="source" 
            position={Position.Right} 
            id="false" 
            style={{ top: '85%', background: '#f43f5e', width: 8, height: 8 }} 
          />
        </div>
      </div>
    </div>
  );
};

export const nodeTypes = {
  trigger: TriggerNode,
  agent: AgentNode,
  condition: ConditionNode,
  action: ActionNode,
  triage: TriageNode
};
