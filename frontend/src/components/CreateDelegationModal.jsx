import React, { useState, useEffect } from 'react';
import { delegationsApi } from '../api/delegations';
import { agentsApi } from '../api/agents';
import { useAuth } from '../context/AuthContext';

export const CreateDelegationModal = ({ onClose, onSuccess }) => {
  const { orgId } = useAuth();
  const [agents, setAgents] = useState([]);
  const [templates, setTemplates] = useState([]);
  
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [purpose, setPurpose] = useState('');
  const [capabilities, setCapabilities] = useState([]); // { code, permission: 'ALLOWED' | 'DENIED' }
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [agentsData, templatesData] = await Promise.all([
          agentsApi.getAgents(),
          agentsApi.getTemplates()
        ]);
        setAgents(agentsData.filter(a => a.status === 'active'));
        setTemplates(templatesData);
      } catch (err) {
        setError('Failed to load agents or available actions');
      }
    };
    fetchData();
  }, []);

  const handleAgentChange = (e) => {
    const agentId = e.target.value;
    setSelectedAgentId(agentId);
    setError(null);
    
    if (agentId) {
      const agent = agents.find(a => a.id === agentId);
      const template = templates.find(t =>
        t.template_id === agent?.template_id &&
        t.template_version === agent?.template_version
      );
      
      if (template && template.tools) {
        setCapabilities(template.tools.map(tool => ({
          code: tool.capability_code,
          name: tool.name,
          permission: 'DENIED'
        })));
      } else {
        setCapabilities([]);
        setError('The selected agent has no registered actions.');
      }
    } else {
      setCapabilities([]);
    }
  };

  const handlePermissionChange = (code, permission) => {
    setCapabilities(caps => caps.map(c => 
      c.code === code ? { ...c, permission } : c
    ));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedAgentId || !purpose) {
      setError('Please fill in all required fields');
      return;
    }
    if (capabilities.length === 0) {
      setError('Select an agent with available actions before creating a delegation.');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      // Calculate next week for expiry
      const expiresAt = new Date();
      expiresAt.setDate(expiresAt.getDate() + 7);
      
      const delegationData = {
        delegator_organization_id: orgId,
        delegatee_agent_id: selectedAgentId,
        purpose,
        starts_at: new Date().toISOString(),
        expires_at: expiresAt.toISOString(),
        capabilities: capabilities.map(c => ({
          capability_code: c.code,
          scope: { permission: c.permission },
          constraints: {}
        }))
      };

      await delegationsApi.createDelegation(delegationData);
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create delegation');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center" style={{ backgroundColor: 'rgba(0,0,0,0.7)', zIndex: 1050 }}>
      <div className="card bg-dark border-secondary shadow-lg w-100" style={{ maxWidth: '600px', maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="card-header border-secondary d-flex justify-content-between align-items-center bg-transparent py-3">
          <h5 className="mb-0 text-light"><i className="bi bi-shield-plus me-2 text-primary"></i>Grant Authority</h5>
          <button className="btn-close btn-close-white" onClick={onClose}></button>
        </div>
        <div className="card-body">
          {error && <div className="alert alert-danger py-2">{error}</div>}
          <form onSubmit={handleSubmit}>
            <div className="mb-3">
              <label className="form-label text-light">Delegatee Agent</label>
              <select className="form-select bg-dark border-secondary text-light" value={selectedAgentId} onChange={handleAgentChange} required>
                <option value="">Select an Agent...</option>
                {agents.map(agent => (
                  <option key={agent.id} value={agent.id}>{agent.name} ({agent.agent_type})</option>
                ))}
              </select>
            </div>
            
            <div className="mb-3">
              <label className="form-label text-light">Purpose</label>
              <input type="text" className="form-control bg-dark border-secondary text-light" value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="e.g. Employee Onboarding" required />
            </div>

            {capabilities.length > 0 && (
              <div className="mb-4">
                <label className="form-label text-light">Capabilities Configuration</label>
                <div className="alert alert-info py-2 small">
                  Select only the actions this organization is granting to the agent.
                </div>
                <div className="list-group">
                  {capabilities.map((cap) => (
                    <div key={cap.code} className="list-group-item bg-darker border-secondary d-flex justify-content-between align-items-center">
                      <div>
                        <div className="text-light fw-bold">{cap.name}</div>
                        <div className="text-muted small font-monospace">{cap.code}</div>
                      </div>
                      <select 
                        className={`form-select form-select-sm w-auto ${cap.permission === 'ALLOWED' ? 'text-success border-success' : 'text-danger border-danger'} bg-dark`}
                        value={cap.permission} 
                        onChange={(e) => handlePermissionChange(cap.code, e.target.value)}
                      >
                        <option value="ALLOWED">ALLOWED</option>
                        <option value="DENIED">DENIED</option>
                      </select>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            <div className="d-flex justify-content-end gap-2">
              <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={loading || !selectedAgentId}>
                {loading ? <span className="spinner-border spinner-border-sm"></span> : 'Grant Authority'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
