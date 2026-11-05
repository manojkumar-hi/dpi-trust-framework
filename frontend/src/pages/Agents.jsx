import React, { useState, useEffect, useMemo, useRef } from 'react';
import { agentsApi } from '../api/agents';
import { trustApi } from '../api/trust';
import { LoadingState } from '../components/common/LoadingState';
import { StatusBadge } from '../components/common/StatusBadge';
import { StatCard } from '../components/common/StatCard';
import { RegisterTemplateModal } from '../components/RegisterTemplateModal';
import { useAuth } from '../context/AuthContext';
import { AgentInteractionModal } from '../components/AgentInteractionModal';

const AgentDetailsModal = ({ agent, onClose }) => {
  const [trustData, setTrustData] = useState(null);
  const [trustLoading, setTrustLoading] = useState(false);
  const [trustError, setTrustError] = useState(null);
  const [authDecision, setAuthDecision] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState(null);
  const modalRef = useRef(null);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    // Prevent background scrolling
    document.body.style.overflow = 'hidden';
    
    // Focus modal for accessibility
    if (modalRef.current) {
      modalRef.current.focus();
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'auto';
    };
  }, [onClose]);

  const handleEvaluateTrust = async () => {
    try {
      setTrustLoading(true);
      setTrustError(null);
      const data = await trustApi.getTrustScore(agent.id);
      setTrustData(data);
    } catch (err) {
      if (!err.response) {
        setTrustError('Backend Offline: Cannot retrieve trust data');
      } else if (err.response.status === 401 || err.response.status === 403) {
        setTrustError('Authentication required to view trust');
      } else {
        setTrustError(`Error ${err.response.status}: Failed to load trust data`);
      }
    } finally {
      setTrustLoading(false);
    }
  };

  const handleRequestAuthorization = async () => {
    try {
      setAuthLoading(true);
      setAuthError(null);
      setAuthDecision(null);
      const data = await agentsApi.requestAuthorization(agent.id);
      setAuthDecision(data);
    } catch (err) {
      if (!err.response) {
        setAuthError('Backend Offline: Cannot perform authorization check.');
      } else if (err.response.status === 401 || err.response.status === 403) {
        setAuthError('Authentication required. Configure a JWT token in the top bar.');
      } else if (err.response.status === 404) {
        setAuthError('Agent not found.');
      } else {
        // For authorization decisions, a 403 from the engine returns the decision
        const detail = err.response.data?.detail;
        setAuthError(`Authorization check error: ${detail || err.response.status}`);
      }
    } finally {
      setAuthLoading(false);
    }
  };

  if (!agent) return null;

  return (
    <div 
      className="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center" 
      style={{ backgroundColor: 'rgba(0,0,0,0.7)', zIndex: 1050 }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      tabIndex="-1"
      ref={modalRef}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="card bg-dark border-secondary shadow-lg w-100" style={{ maxWidth: '600px', maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="card-header border-secondary d-flex justify-content-between align-items-center bg-transparent py-3">
          <h5 className="mb-0 text-light" id="modal-title">
            <i className="bi bi-robot me-2 text-primary"></i>
            Agent Details
          </h5>
          <button className="btn-close btn-close-white" onClick={onClose} aria-label="Close"></button>
        </div>
        <div className="card-body">
          <div className="row mb-3">
            <div className="col-12">
              <h4 className="text-white mb-1">{agent.name}</h4>
              <p className="text-muted mb-2">{agent.description || 'No description available.'}</p>
              <StatusBadge status={agent.status} />
            </div>
          </div>
          
          <div className="row mb-4">
            <div className="col-12">
              <table className="table table-dark table-sm table-borderless mb-0">
                <tbody>
                  <tr>
                    <td className="text-muted w-25">Agent ID</td>
                    <td className="font-monospace small">{agent.id}</td>
                  </tr>
                  <tr>
                    <td className="text-muted">Type</td>
                    <td><span className="badge bg-secondary">{agent.agent_type}</span></td>
                  </tr>
                  <tr>
                    <td className="text-muted">Org ID</td>
                    <td className="font-monospace small">{agent.organization_id}</td>
                  </tr>
                  <tr>
                    <td className="text-muted">Created</td>
                    <td>{new Date(agent.created_at).toLocaleString()}</td>
                  </tr>
                  {agent.updated_at && (
                    <tr>
                      <td className="text-muted">Updated</td>
                      <td>{new Date(agent.updated_at).toLocaleString()}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card bg-darker border-secondary mb-0">
            <div className="card-header border-secondary bg-transparent d-flex justify-content-between align-items-center">
              <h6 className="mb-0 text-light"><i className="bi bi-shield-check me-2"></i>Trust Evaluation</h6>
              {!trustData && !trustLoading && (
                <button className="btn btn-sm btn-outline-primary" onClick={handleEvaluateTrust}>
                  Evaluate Trust
                </button>
              )}
            </div>
            <div className="card-body">
              {trustLoading && (
                <div className="text-center py-3">
                  <div className="spinner-border spinner-border-sm text-primary me-2" role="status"></div>
                  <span className="text-muted small">Computing trust score...</span>
                </div>
              )}
              {trustError && (
                <div className="alert alert-danger py-2 px-3 mb-0 small">
                  <i className="bi bi-exclamation-triangle me-2"></i>{trustError}
                </div>
              )}
              {trustData && (
                <div className="row text-center">
                  <div className="col-4 mb-2">
                    <div className="text-muted small text-uppercase">Trust Score</div>
                    <div className="fs-3 fw-bold text-light">{((trustData.trust ?? 0) * 100).toFixed(1)}%</div>
                  </div>
                  <div className="col-8 mb-2 d-flex justify-content-around align-items-center">
                    <div>
                      <div className="text-muted small">Belief</div>
                      <div className="text-light">{(trustData.belief * 100).toFixed(1)}%</div>
                    </div>
                    <div>
                      <div className="text-muted small">Disbelief</div>
                      <div className="text-light">{(trustData.disbelief * 100).toFixed(1)}%</div>
                    </div>
                    <div>
                      <div className="text-muted small">Uncertainty</div>
                      <div className="text-light">{(trustData.uncertainty * 100).toFixed(1)}%</div>
                    </div>
                  </div>
                  {trustData.recent_risk !== undefined && (
                    <div className="col-12 text-center mt-2 pt-2 border-top border-secondary">
                      <span className="text-muted small me-2">Recent Risk:</span>
                      <span className="text-light">{(trustData.recent_risk * 100).toFixed(1)}%</span>
                    </div>
                  )}
                </div>
              )}
              {!trustData && !trustLoading && !trustError && (
                <p className="text-muted small mb-0 text-center py-2">
                  Click 'Evaluate Trust' to retrieve dynamic trust metrics for this agent.
                </p>
              )}
            </div>
          </div>

          {/* Authorization Decision Section */}
          <div className="card bg-darker border-secondary mt-3 mb-0">
            <div className="card-header border-secondary bg-transparent d-flex justify-content-between align-items-center">
              <h6 className="mb-0 text-light"><i className="bi bi-diagram-3 me-2"></i>Authorization Decision</h6>
              <button
                id="request-auth-btn"
                className="btn btn-sm btn-outline-warning"
                onClick={handleRequestAuthorization}
                disabled={authLoading}
              >
                {authLoading
                  ? <><span className="spinner-border spinner-border-sm me-1" role="status"></span>Checking...</>
                  : <><i className="bi bi-lightning me-1"></i>Request Authorization</>}
              </button>
            </div>
            <div className="card-body">
              {authError && (
                <div className="alert alert-danger py-2 px-3 mb-0 small">
                  <i className="bi bi-exclamation-triangle me-2"></i>{authError}
                </div>
              )}
              {authDecision && (
                <div>
                  <div className={`alert ${authDecision.decision?.reason_code === 'ALLOW' || authDecision.message?.includes('success') ? 'alert-success' : 'alert-danger'} d-flex align-items-center py-2 mb-2`}>
                    <i className={`bi ${authDecision.decision?.reason_code === 'ALLOW' ? 'bi-shield-check-fill' : 'bi-shield-x-fill'} fs-4 me-3`}></i>
                    <div>
                      <strong className="d-block">
                        {authDecision.decision?.reason_code === 'ALLOW' ? 'ALLOW' : 'DENY'}
                      </strong>
                      <span className="small">{authDecision.message}</span>
                    </div>
                  </div>
                  <table className="table table-dark table-sm table-borderless mb-0">
                    <tbody>
                      <tr>
                        <td className="text-muted small w-25">Reason Code</td>
                        <td><span className="badge bg-secondary font-monospace">{authDecision.decision?.reason_code}</span></td>
                      </tr>
                      <tr>
                        <td className="text-muted small">Explanation</td>
                        <td className="text-light small">{authDecision.decision?.explanation}</td>
                      </tr>
                      <tr>
                        <td className="text-muted small">Agent ID</td>
                        <td className="font-monospace small text-muted">{agent.id}</td>
                      </tr>
                      <tr>
                        <td className="text-muted small">Resource</td>
                        <td><span className="badge bg-dark border border-secondary text-light">verifiable_credential:issue</span></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
              {!authDecision && !authLoading && !authError && (
                <p className="text-muted small mb-0 text-center py-2">
                  Click 'Request Authorization' to evaluate trust-based access decision for this agent.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export const Agents = () => {
  const { orgId } = useAuth();
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Filtering states
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  
  // Modal state
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [interactionAgent, setInteractionAgent] = useState(null);
  const [showRegisterTemplate, setShowRegisterTemplate] = useState(false);

  useEffect(() => {
    if (!orgId) return undefined;
    let isMounted = true;
    
    const fetchAgents = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await agentsApi.getAgents(orgId);
        if (isMounted) {
          setAgents(data);
        }
      } catch (err) {
        if (isMounted) {
          if (!err.response) {
            setError({ type: 'network', message: 'Backend Offline: Cannot retrieve agents' });
          } else if (err.response.status === 401 || err.response.status === 403) {
            setError({ type: 'auth', message: 'Authentication required to view agents' });
          } else {
            setError({ type: 'api', message: `Error ${err.response.status}: Failed to load agents` });
          }
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchAgents();
    
    return () => {
      isMounted = false;
    };
  }, [orgId]);

  // Derived stats
  const totalAgents = agents.length;
  const activeAgents = agents.filter(a => a.status === 'active').length;
  const inactiveAgents = agents.filter(a => a.status !== 'active').length;

  // Unique statuses for filter dropdown (if API returns other statuses)
  const uniqueStatuses = ['All', ...new Set(agents.map(a => a.status))];

  // Filtering logic
  const filteredAgents = useMemo(() => {
    return agents.filter(agent => {
      const matchesSearch = agent.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                            agent.agent_type.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'All' || agent.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [agents, searchTerm, statusFilter]);

  return (
    <div className="container-fluid position-relative">
      <style>{`
        .bg-darker { background-color: #1a1d20 !important; }
        .table-hover tbody tr:hover { background-color: rgba(255, 255, 255, 0.05); }
        .text-truncate-uuid { max-width: 150px; display: inline-block; }
      `}</style>
      
      <div className="row mb-4">
        <div className="col-12">
          <h2 className="mb-1 fw-bold">Agent Registry</h2>
          <p className="text-muted fs-6">Manage and inspect AI agents registered in the decentralized trust framework.</p>
        </div>
      </div>
      
      {loading ? (
        <LoadingState message="Loading agent registry..." />
      ) : error ? (
        <div className="card bg-dark border-secondary text-center p-5 shadow-sm">
          <i className="bi bi-exclamation-triangle text-warning fs-1 mb-3"></i>
          <p className={`mb-0 ${error.type === 'network' ? 'text-danger' : 'text-warning'}`}>{error.message}</p>
        </div>
      ) : (
        <>
          <div className="row mb-4">
            <div className="col-md-4">
              <StatCard title="Total Agents" value={totalAgents} icon="robot" />
            </div>
            <div className="col-md-4">
              <StatCard title="Active Agents" value={activeAgents} icon="check-circle" />
            </div>
            <div className="col-md-4">
              <StatCard title="Inactive Agents" value={inactiveAgents} icon="x-circle" />
            </div>
          </div>

          <div className="card bg-dark border-secondary shadow-sm">
            <div className="card-header border-secondary bg-transparent py-3 d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3">
              <div className="d-flex align-items-center justify-content-between w-100">
                <h6 className="mb-0 fw-semibold text-light"><i className="bi bi-list-ul me-2"></i>Registered Agents</h6>
                <button className="btn btn-sm btn-primary" onClick={() => setShowRegisterTemplate(true)}><i className="bi bi-plus-circle me-1"></i>Register Agent</button>
              </div>
              <div className="d-flex flex-column flex-md-row gap-2">
                <div className="input-group input-group-sm" style={{ width: '250px' }}>
                  <span className="input-group-text bg-dark border-secondary text-muted"><i className="bi bi-search"></i></span>
                  <input 
                    type="text" 
                    className="form-control bg-dark border-secondary text-light" 
                    placeholder="Search name or type..." 
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <select 
                  className="form-select form-select-sm bg-dark border-secondary text-light" 
                  style={{ width: '150px' }}
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  {uniqueStatuses.map(status => (
                    <option key={status} value={status}>
                      {status === 'All' ? 'All Statuses' : status.charAt(0).toUpperCase() + status.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            
            <div className="card-body p-0">
              {filteredAgents.length === 0 ? (
                <div className="text-center p-5">
                  <i className="bi bi-search text-muted fs-1 mb-3 d-block"></i>
                  <p className="text-muted mb-0">No agents match your search criteria.</p>
                </div>
              ) : (
                <div className="table-responsive">
                  <table className="table table-dark table-hover mb-0 align-middle">
                    <thead>
                      <tr>
                        <th className="border-secondary px-3 py-3">Agent Name</th>
                        <th className="border-secondary py-3">Type</th>
                        <th className="border-secondary py-3">Status</th>
                        <th className="border-secondary py-3">Organization ID</th>
                        <th className="border-secondary py-3">Registered</th>
                        <th className="border-secondary px-3 py-3 text-end">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredAgents.map(agent => (
                        <tr key={agent.id}>
                          <td className="border-secondary px-3">
                            <div className="d-flex align-items-center">
                              <div className="bg-primary bg-opacity-10 p-2 rounded me-3">
                                <i className="bi bi-robot text-primary"></i>
                              </div>
                              <div>
                                <strong className="d-block text-light">{agent.name}</strong>
                                <span className="font-monospace text-muted small text-truncate-uuid text-truncate" title={agent.id}>{agent.id}</span>
                              </div>
                            </div>
                          </td>
                          <td className="border-secondary"><span className="badge bg-secondary">{agent.agent_type}</span></td>
                          <td className="border-secondary"><StatusBadge status={agent.status} /></td>
                          <td className="border-secondary font-monospace text-muted small text-truncate-uuid text-truncate" title={agent.organization_id}>{agent.organization_id}</td>
                          <td className="border-secondary text-muted small">{new Date(agent.created_at).toLocaleDateString()}</td>
                          <td className="border-secondary px-3 text-end">
                            {agent.template_id && (
                              <button className="btn btn-sm btn-primary me-2" onClick={() => setInteractionAgent(agent)}>
                                <i className="bi bi-chat-dots me-1"></i>Try agent
                              </button>
                            )}
                            <button 
                              className="btn btn-sm btn-outline-light" 
                              onClick={() => setSelectedAgent(agent)}
                            >
                              View
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {selectedAgent && (
        <AgentDetailsModal 
          agent={selectedAgent} 
          onClose={() => setSelectedAgent(null)} 
        />
      )}
      {interactionAgent && <AgentInteractionModal agent={interactionAgent} onClose={() => setInteractionAgent(null)} />}
      {showRegisterTemplate && (
        <RegisterTemplateModal
          onClose={() => setShowRegisterTemplate(false)}
          onSuccess={async () => {
            try {
              setAgents(await agentsApi.getAgents(orgId));
            } catch {
              setError({ type: 'api', message: 'The agent was registered, but the registry could not be refreshed.' });
            }
          }}
        />
      )}
    </div>
  );
};
