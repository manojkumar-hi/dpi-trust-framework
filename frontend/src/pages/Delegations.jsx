import React, { useState, useEffect, useMemo, useRef } from 'react';
import { delegationsApi } from '../api/delegations';
import { agentsApi } from '../api/agents';
import { LoadingState } from '../components/common/LoadingState';
import { StatusBadge } from '../components/common/StatusBadge';
import { StatCard } from '../components/common/StatCard';
import { CreateDelegationModal } from '../components/CreateDelegationModal';
import { useAuth } from '../context/AuthContext';

const DelegationDetailsModal = ({ delegation, onClose, onRevoked }) => {
  const [verifyResult, setVerifyResult] = useState(null);
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [verifyError, setVerifyError] = useState(null);
  
  const [chainResult, setChainResult] = useState(null);
  const [chainLoading, setChainLoading] = useState(false);
  const [chainError, setChainError] = useState(null);
  const [showChain, setShowChain] = useState(false);
  const [revokeLoading, setRevokeLoading] = useState(false);
  const [revokeError, setRevokeError] = useState(null);

  const modalRef = useRef(null);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';
    
    if (modalRef.current) {
      modalRef.current.focus();
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'auto';
    };
  }, [onClose]);

  const handleVerify = async () => {
    try {
      setVerifyLoading(true);
      setVerifyError(null);
      const data = await delegationsApi.verifyDelegation(delegation.id);
      setVerifyResult(data);
    } catch (err) {
      if (!err.response) {
        setVerifyError('Backend Offline: Cannot reach verification service');
      } else if (err.response.status === 401 || err.response.status === 403) {
        setVerifyError('Authentication/Authorization Required: You do not have permission to verify this delegation.');
      } else {
        setVerifyError(`Verification Error (${err.response.status}): ${err.response.data?.detail || 'Failed to verify'}`);
      }
    } finally {
      setVerifyLoading(false);
    }
  };

  const handleViewChain = async () => {
    if (showChain) {
      setShowChain(false);
      return;
    }
    
    try {
      setChainLoading(true);
      setChainError(null);
      const data = await delegationsApi.getDelegationChain(delegation.id);
      setChainResult(data);
      setShowChain(true);
    } catch (err) {
      if (!err.response) {
        setChainError('Backend Offline: Cannot retrieve chain');
      } else if (err.response.status === 401 || err.response.status === 403) {
        setChainError('Authentication/Authorization Required: You do not have permission to view this chain.');
      } else {
        setChainError(`Chain Retrieval Error (${err.response.status}): ${err.response.data?.detail || 'Failed to retrieve chain'}`);
      }
    } finally {
      setChainLoading(false);
    }
  };

  const handleRevoke = async () => {
    const reason = window.prompt('Why are you revoking this delegation?', 'No longer required');
    if (!reason?.trim()) return;
    try {
      setRevokeLoading(true);
      setRevokeError(null);
      const revoked = await delegationsApi.revokeDelegation(delegation.id, reason.trim());
      onRevoked(revoked);
      onClose();
    } catch (err) {
      setRevokeError(err.response?.data?.detail || 'The delegation could not be revoked.');
    } finally {
      setRevokeLoading(false);
    }
  };

  if (!delegation) return null;

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
      <div className="card bg-dark border-secondary shadow-lg w-100" style={{ maxWidth: '900px', maxHeight: '95vh', overflowY: 'auto' }}>
        <div className="card-header border-secondary d-flex justify-content-between align-items-center bg-transparent py-3">
          <h5 className="mb-0 text-light" id="modal-title">
            <i className="bi bi-diagram-3 me-2 text-primary"></i>
            Delegation Details
          </h5>
          <button className="btn-close btn-close-white" onClick={onClose} aria-label="Close"></button>
        </div>
        <div className="card-body">
          <div className="row mb-4">
            <div className="col-md-6 mb-3 mb-md-0">
              <h6 className="text-light border-bottom border-secondary pb-2"><i className="bi bi-person-badge me-2"></i>Authority</h6>
              <table className="table table-dark table-sm table-borderless mb-0">
                <tbody>
                  <tr>
                    <td className="text-muted w-25">ID</td>
                    <td className="font-monospace small text-truncate" style={{maxWidth: '250px'}} title={delegation.id}>{delegation.id}</td>
                  </tr>
                  <tr>
                    <td className="text-muted">Delegator Org</td>
                    <td className="font-monospace small text-truncate" style={{maxWidth: '250px'}} title={delegation.delegator_organization_id}>{delegation.delegator_organization_id}</td>
                  </tr>
                  {delegation.delegator_did && (
                    <tr>
                      <td className="text-muted">Delegator DID</td>
                      <td className="font-monospace small text-truncate" style={{maxWidth: '250px'}} title={delegation.delegator_did}>{delegation.delegator_did}</td>
                    </tr>
                  )}
                  <tr>
                    <td className="text-muted">Delegatee Agent</td>
                    <td className="font-monospace small text-truncate" style={{maxWidth: '250px'}} title={delegation.delegatee_agent_id}>{delegation.delegatee_agent_id}</td>
                  </tr>
                  {delegation.delegatee_did && (
                    <tr>
                      <td className="text-muted">Delegatee DID</td>
                      <td className="font-monospace small text-truncate" style={{maxWidth: '250px'}} title={delegation.delegatee_did}>{delegation.delegatee_did}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="col-md-6">
              <h6 className="text-light border-bottom border-secondary pb-2"><i className="bi bi-diagram-2 me-2"></i>Relationship & Lifecycle</h6>
              <table className="table table-dark table-sm table-borderless mb-0">
                <tbody>
                  <tr>
                    <td className="text-muted w-25">Purpose</td>
                    <td className="small text-light">{delegation.purpose}</td>
                  </tr>
                  <tr>
                    <td className="text-muted">Status</td>
                    <td><StatusBadge status={delegation.status} /></td>
                  </tr>
                  {delegation.parent_delegation_id && (
                    <tr>
                      <td className="text-muted">Parent ID</td>
                      <td className="font-monospace small text-truncate" style={{maxWidth: '200px'}} title={delegation.parent_delegation_id}>{delegation.parent_delegation_id}</td>
                    </tr>
                  )}
                  {delegation.root_delegation_id && (
                    <tr>
                      <td className="text-muted">Root ID</td>
                      <td className="font-monospace small text-truncate" style={{maxWidth: '200px'}} title={delegation.root_delegation_id}>{delegation.root_delegation_id}</td>
                    </tr>
                  )}
                  <tr>
                    <td className="text-muted">Starts</td>
                    <td className="small">{new Date(delegation.starts_at).toLocaleString()}</td>
                  </tr>
                  <tr>
                    <td className="text-muted">Expires</td>
                    <td className="small">{delegation.expires_at ? new Date(delegation.expires_at).toLocaleString() : 'Never'}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="mb-4">
            <h6 className="text-light border-bottom border-secondary pb-2"><i className="bi bi-list-check me-2"></i>Capabilities & Constraints</h6>
            {delegation.capabilities && delegation.capabilities.length > 0 ? (
              <div className="list-group list-group-flush border border-secondary rounded">
                {delegation.capabilities.map((cap, idx) => (
                  <div key={idx} className="list-group-item bg-darker text-light border-secondary p-3">
                    <div className="mb-2">
                      <span className="badge bg-primary text-light me-2">{cap.capability_code}</span>
                    </div>
                    <div className="row">
                      <div className="col-md-6">
                        <div className="text-muted small mb-1">Scope</div>
                        {cap.scope && Object.keys(cap.scope).length > 0 ? (
                          <pre className="bg-black p-2 rounded border border-secondary text-info mb-0 font-monospace" style={{ fontSize: '0.75rem', maxHeight: '150px', overflowY: 'auto' }}>
                            {JSON.stringify(cap.scope, null, 2)}
                          </pre>
                        ) : (
                          <div className="small text-muted fst-italic">Global Scope</div>
                        )}
                      </div>
                      <div className="col-md-6 mt-2 mt-md-0">
                        <div className="text-muted small mb-1">Constraints</div>
                        {cap.constraints && Object.keys(cap.constraints).length > 0 ? (
                          <pre className="bg-black p-2 rounded border border-secondary text-warning mb-0 font-monospace" style={{ fontSize: '0.75rem', maxHeight: '150px', overflowY: 'auto' }}>
                            {JSON.stringify(cap.constraints, null, 2)}
                          </pre>
                        ) : (
                          <div className="small text-muted fst-italic">No constraints</div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-muted small fst-italic">No capabilities defined.</div>
            )}
          </div>

          <div className="row mb-4">
            <div className="col-12">
              <h6 className="text-light border-bottom border-secondary pb-2"><i className="bi bi-shield-lock me-2"></i>Cryptographic Proof</h6>
              <table className="table table-dark table-sm table-borderless mb-0">
                <tbody>
                  <tr>
                    <td className="text-muted" style={{width: '200px'}}>Proof Type</td>
                    <td className="small">{delegation.proof_type || 'N/A'}</td>
                  </tr>
                  <tr>
                    <td className="text-muted">Signature Presence</td>
                    <td className="small">
                      {delegation.signature ? <span className="text-success"><i className="bi bi-check-circle me-1"></i>Present</span> : <span className="text-warning"><i className="bi bi-exclamation-circle me-1"></i>None</span>}
                    </td>
                  </tr>
                  <tr>
                    <td className="text-muted">Canonical Hash</td>
                    <td className="font-monospace small text-truncate" style={{maxWidth: '400px'}} title={delegation.canonical_hash}>{delegation.canonical_hash || 'N/A'}</td>
                  </tr>
                  {delegation.transaction_id && (
                    <tr>
                      <td className="text-muted">Transaction ID</td>
                      <td className="font-monospace small text-truncate" style={{maxWidth: '400px'}} title={delegation.transaction_id}>{delegation.transaction_id}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card bg-darker border-secondary mb-3 shadow-sm">
            <div className="card-header border-secondary bg-transparent d-flex justify-content-between align-items-center flex-wrap gap-2">
              <h6 className="mb-0 text-light"><i className="bi bi-check2-circle me-2"></i>Delegation Verification</h6>
              <div>
                {delegation.status === 'active' && (
                  <button className="btn btn-sm btn-outline-danger me-2" onClick={handleRevoke} disabled={revokeLoading}>
                    {revokeLoading ? 'Revoking…' : 'Revoke Delegation'}
                  </button>
                )}
                <button className="btn btn-sm btn-outline-info me-2" onClick={handleViewChain} disabled={chainLoading}>
                  {chainLoading ? <span className="spinner-border spinner-border-sm" role="status"></span> : (showChain ? 'Hide Chain' : 'View Chain')}
                </button>
                <button className="btn btn-sm btn-primary" onClick={handleVerify} disabled={verifyLoading}>
                  {verifyLoading ? <span className="spinner-border spinner-border-sm" role="status"></span> : 'Verify Delegation'}
                </button>
              </div>
            </div>

            {chainError && (
              <div className="card-body bg-danger bg-opacity-10 border-bottom border-secondary">
                <div className="text-danger small"><i className="bi bi-exclamation-triangle me-2"></i>{chainError}</div>
              </div>
            )}
            
            {showChain && chainResult && (
              <div className="card-body border-bottom border-secondary bg-black">
                <h6 className="text-muted small mb-3">Delegation Chain</h6>
                {Array.isArray(chainResult) && chainResult.length > 0 ? (
                  <div className="d-flex flex-column align-items-start ms-3">
                    {chainResult.map((node, index) => (
                      <div key={node.id || index} className="position-relative mb-3">
                        {index > 0 && (
                          <div className="position-absolute border-start border-2 border-secondary" style={{ left: '-15px', top: '-25px', height: '30px' }}></div>
                        )}
                        <div className={`p-2 rounded border ${node.id === delegation.id ? 'border-primary bg-primary bg-opacity-10' : 'border-secondary bg-dark'}`}>
                          <div className="font-monospace small">{node.id || 'Unknown ID'}</div>
                          <div className="small text-muted">{node.purpose || 'No purpose'}</div>
                          {node.id === delegation.id && <span className="badge bg-primary mt-1">Current</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-2 rounded border border-primary bg-primary bg-opacity-10 d-inline-block">
                    <div className="font-monospace small">{delegation.id}</div>
                    <div className="small text-muted">{delegation.purpose}</div>
                    <span className="badge bg-primary mt-1">Root / Current</span>
                  </div>
                )}
              </div>
            )}

            {verifyError && (
              <div className="card-body bg-danger bg-opacity-10">
                <div className="text-danger small"><i className="bi bi-exclamation-triangle me-2"></i>{verifyError}</div>
              </div>
            )}

            {revokeError && (
              <div className="card-body bg-danger bg-opacity-10">
                <div className="text-danger small"><i className="bi bi-exclamation-triangle me-2"></i>{revokeError}</div>
              </div>
            )}

            {verifyResult && (
              <div className="card-body">
                <div className="row">
                  <div className="col-md-6 border-end border-secondary">
                    <h6 className="text-light mb-3">Cryptographic & Lifecycle</h6>
                    <div className="d-flex align-items-center mb-2">
                      <i className={`bi fs-4 me-3 ${verifyResult.valid ? 'bi-shield-check text-success' : 'bi-shield-x text-danger'}`}></i>
                      <div>
                        <div className={`fw-bold ${verifyResult.valid ? 'text-success' : 'text-danger'}`}>
                          {verifyResult.valid ? 'Valid Delegation' : 'Invalid Delegation'}
                        </div>
                        <div className="text-muted small">{verifyResult.reason_code || 'Delegation check'}</div>
                      </div>
                    </div>
                  </div>
                  <div className="col-md-6 ps-md-4">
                    <h6 className="text-light mb-3">Local Registry State</h6>
                    <div className="mb-2">
                      <div className="text-muted small">Local Status</div>
                      <div>
                        <StatusBadge status={verifyResult.local_status || delegation.status} />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export const Delegations = () => {
  const { orgId } = useAuth();
  const [delegations, setDelegations] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Filtering states
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  
  // Modal state
  const [selectedDelegation, setSelectedDelegation] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    let isMounted = true;
    
    const fetchDelegations = async () => {
      try {
        setLoading(true);
        setError(null);
        const [data, agentRecords] = await Promise.all([
          delegationsApi.getDelegations(),
          agentsApi.getAgents(orgId),
        ]);
        if (isMounted) {
          setDelegations(data);
          setAgents(agentRecords);
        }
      } catch (err) {
        if (isMounted) {
          if (!err.response) {
            setError({ type: 'network', message: 'Backend Offline: Cannot retrieve delegations' });
          } else if (err.response.status === 401 || err.response.status === 403) {
            setError({ type: 'auth', message: 'Authentication required to view delegations' });
          } else {
            setError({ type: 'api', message: `Error ${err.response.status}: Failed to load delegations` });
          }
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchDelegations();
    
    return () => {
      isMounted = false;
    };
  }, [orgId, showCreateModal]);

  // Derived stats
  const totalDels = delegations.length;
  const activeDels = delegations.filter(d => d.status === 'active').length;
  const revokedDels = delegations.filter(d => d.status === 'revoked').length;
  const expiredDels = delegations.filter(d => d.status === 'expired').length;

  const uniqueStatuses = ['All', ...new Set(delegations.map(d => d.status))];

  // Filtering logic
  const filteredDelegations = useMemo(() => {
    return delegations.filter(del => {
      const lowerSearch = searchTerm.toLowerCase();
      const capabilitiesText = (del.capabilities || []).map(c => c.capability_code).join(' ').toLowerCase();
      
      const matchesSearch = 
        del.id.toLowerCase().includes(lowerSearch) || 
        del.delegator_organization_id?.toLowerCase().includes(lowerSearch) ||
        del.delegator_did?.toLowerCase().includes(lowerSearch) ||
        del.delegatee_agent_id?.toLowerCase().includes(lowerSearch) ||
        del.delegatee_did?.toLowerCase().includes(lowerSearch) ||
        del.purpose.toLowerCase().includes(lowerSearch) ||
        capabilitiesText.includes(lowerSearch);
        
      const matchesStatus = statusFilter === 'All' || del.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [delegations, searchTerm, statusFilter]);

  const agentName = (agentId) => agents.find((agent) => agent.id === agentId)?.name || 'Unknown agent';

  return (
    <div className="container-fluid position-relative">
      <style>{`
        .bg-darker { background-color: #1a1d20 !important; }
        .table-hover tbody tr:hover { background-color: rgba(255, 255, 255, 0.05); }
        .text-truncate-uuid { max-width: 130px; display: inline-block; vertical-align: middle; }
      `}</style>
      
      <div className="row mb-4">
        <div className="col-12 d-flex justify-content-between align-items-center">
          <div>
            <h2 className="mb-1 fw-bold">Delegation & Authority</h2>
            <p className="text-muted fs-6 mb-0">Delegated capabilities and authority relationships within the trust framework.</p>
          </div>
          <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
            <i className="bi bi-shield-plus me-2"></i>Grant Authority
          </button>
        </div>
      </div>

      
      {loading ? (
        <LoadingState message="Loading delegation registry..." />
      ) : error ? (
        <div className="card bg-dark border-secondary text-center p-5 shadow-sm">
          <i className="bi bi-exclamation-triangle text-warning fs-1 mb-3"></i>
          <p className={`mb-0 ${error.type === 'network' ? 'text-danger' : 'text-warning'}`}>{error.message}</p>
        </div>
      ) : (
        <>
          <div className="row mb-4">
            <div className="col-md-3">
              <StatCard title="Total Delegations" value={totalDels} icon="diagram-3" />
            </div>
            <div className="col-md-3">
              <StatCard title="Active" value={activeDels} icon="check-circle" />
            </div>
            <div className="col-md-3">
              <StatCard title="Revoked" value={revokedDels} icon="slash-circle" />
            </div>
            <div className="col-md-3">
              <StatCard title="Expired" value={expiredDels} icon="clock-history" />
            </div>
          </div>

          <div className="alert alert-secondary bg-dark border-secondary text-muted small py-2 d-flex align-items-center mb-4 shadow-sm">
            <i className="bi bi-info-circle me-3 fs-4 text-info"></i>
            <div>
              <strong>Delegation establishes delegated authority and capabilities.</strong> Runtime authorization additionally depends on identity, policy, trust, and other security controls.
            </div>
          </div>

          <div className="card bg-dark border-secondary shadow-sm">
            <div className="card-header border-secondary bg-transparent py-3 d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3">
              <h6 className="mb-0 fw-semibold text-light"><i className="bi bi-list-ul me-2"></i>Authority Registry</h6>
              <div className="d-flex flex-column flex-md-row gap-2">
                <div className="input-group input-group-sm" style={{ width: '300px' }}>
                  <span className="input-group-text bg-dark border-secondary text-muted"><i className="bi bi-search"></i></span>
                  <input 
                    type="text" 
                    className="form-control bg-dark border-secondary text-light" 
                    placeholder="Search agent or ID..."
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
              {filteredDelegations.length === 0 ? (
                <div className="text-center p-5">
                  <i className="bi bi-search text-muted fs-1 mb-3 d-block"></i>
                  <p className="text-muted mb-0">No delegations match your search criteria.</p>
                </div>
              ) : (
                <div className="table-responsive">
                  <table className="table table-dark table-hover mb-0 align-middle">
                    <thead>
                      <tr>
                        <th className="border-secondary px-3 py-3">Agent</th>
                        <th className="border-secondary py-3">Status</th>
                        <th className="border-secondary px-3 py-3 text-end">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredDelegations.map(del => (
                        <tr key={del.id}>
                          <td className="border-secondary px-3">
                            <div className="text-light fw-semibold">{agentName(del.delegatee_agent_id)}</div>
                            <span className="font-monospace text-muted small text-truncate-uuid text-truncate" title={del.delegatee_agent_id}>{del.delegatee_agent_id}</span>
                          </td>
                          <td className="border-secondary"><StatusBadge status={del.status} /></td>
                          <td className="border-secondary px-3 text-end">
                            <button 
                              className="btn btn-sm btn-primary fw-semibold px-3 shadow-sm"
                              onClick={() => setSelectedDelegation(del)}
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

      {selectedDelegation && (
        <DelegationDetailsModal 
          delegation={selectedDelegation}
          onClose={() => setSelectedDelegation(null)}
          onRevoked={(revoked) => setDelegations((current) => current.map((item) => item.id === revoked.id ? revoked : item))}
        />
      )}

      {showCreateModal && (
        <CreateDelegationModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => setShowCreateModal(false)}
        />
      )}
    </div>
  );
};
