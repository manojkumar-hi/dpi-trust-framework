import React, { useState, useEffect, useMemo, useRef } from 'react';
import { auditApi } from '../api/audit';
import { LoadingState } from '../components/common/LoadingState';
import { StatCard } from '../components/common/StatCard';

const AuditEventModal = ({ record, onClose }) => {
  const modalRef = useRef(null);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';
    
    if (modalRef.current) modalRef.current.focus();

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'auto';
    };
  }, [onClose]);

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (err) {
      console.error('Failed to copy', err);
    }
  };

  const getDecisionColor = (decision) => {
    if (!decision) return 'bg-secondary';
    const lower = decision.toLowerCase();
    if (lower.includes('allow') || lower.includes('success') || lower.includes('permit')) return 'bg-success';
    if (lower.includes('deny') || lower.includes('fail') || lower.includes('reject')) return 'bg-danger';
    return 'bg-secondary';
  };

  if (!record) return null;

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
        <div className="card-header border-secondary d-flex justify-content-between align-items-center bg-black py-3">
          <h5 className="mb-0 text-light" id="modal-title">
            <i className="bi bi-file-earmark-text text-primary me-2"></i>
            Audit Record Details
          </h5>
          <button className="btn-close btn-close-white" onClick={onClose} aria-label="Close"></button>
        </div>
        
        <div className="card-body">
          <div className="row mb-4">
            <div className="col-md-6 mb-3 mb-md-0">
              <h6 className="text-light border-bottom border-secondary pb-2"><i className="bi bi-info-circle me-2"></i>Event Information</h6>
              <table className="table table-dark table-sm table-borderless mb-0">
                <tbody>
                  <tr>
                    <td className="text-muted w-25 small">Audit ID</td>
                    <td className="font-monospace small text-truncate" style={{maxWidth: '250px'}} title={record.id}>{record.id}</td>
                  </tr>
                  <tr>
                    <td className="text-muted small">Occurred At</td>
                    <td className="small">{new Date(record.occurred_at).toLocaleString()}</td>
                  </tr>
                  <tr>
                    <td className="text-muted small">Category</td>
                    <td className="small">{record.event_category}</td>
                  </tr>
                  <tr>
                    <td className="text-muted small">Type</td>
                    <td className="small">{record.event_type}</td>
                  </tr>
                  <tr>
                    <td className="text-muted small">Version</td>
                    <td className="small">{record.event_version || '1.0'}</td>
                  </tr>
                  {record.correlation_id && (
                    <tr>
                      <td className="text-muted small">Correlation ID</td>
                      <td>
                        <div className="d-flex align-items-center">
                          <span className="font-monospace small text-info text-truncate me-2" style={{maxWidth: '200px'}} title={record.correlation_id}>{record.correlation_id}</span>
                          <button className="btn btn-sm btn-link text-info p-0" onClick={() => copyToClipboard(record.correlation_id)} title="Copy ID">
                            <i className="bi bi-clipboard"></i>
                          </button>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="col-md-6">
              <h6 className="text-light border-bottom border-secondary pb-2"><i className="bi bi-person-badge me-2"></i>Actor Context</h6>
              <table className="table table-dark table-sm table-borderless mb-0">
                <tbody>
                  <tr>
                    <td className="text-muted w-25 small">Actor DID</td>
                    <td className="font-monospace small text-truncate" style={{maxWidth: '250px'}} title={record.actor_did}>{record.actor_did || 'System / None'}</td>
                  </tr>
                  <tr>
                    <td className="text-muted small">Actor Org</td>
                    <td className="font-monospace small text-truncate" style={{maxWidth: '250px'}} title={record.actor_organization_id}>{record.actor_organization_id || 'System / None'}</td>
                  </tr>
                </tbody>
              </table>

              <h6 className="text-light border-bottom border-secondary pb-2 mt-4"><i className="bi bi-box me-2"></i>Subject & Resource</h6>
              <table className="table table-dark table-sm table-borderless mb-0">
                <tbody>
                  <tr>
                    <td className="text-muted w-25 small">Subject Agent</td>
                    <td className="font-monospace small text-truncate" style={{maxWidth: '250px'}} title={record.subject_agent_id}>{record.subject_agent_id || '-'}</td>
                  </tr>
                  <tr>
                    <td className="text-muted small">Resource Type</td>
                    <td className="small">{record.resource_type || '-'}</td>
                  </tr>
                  <tr>
                    <td className="text-muted small">Resource ID</td>
                    <td className="font-monospace small text-truncate" style={{maxWidth: '250px'}} title={record.resource_id}>{record.resource_id || '-'}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="row mb-4">
            <div className="col-12">
              <h6 className="text-light border-bottom border-secondary pb-2"><i className="bi bi-shield-check me-2"></i>Authorization Decision</h6>
              <table className="table table-dark table-sm table-borderless mb-0">
                <tbody>
                  <tr>
                    <td className="text-muted w-25 small">Action Requested</td>
                    <td className="small">{record.action_requested || '-'}</td>
                  </tr>
                  <tr>
                    <td className="text-muted small">Decision</td>
                    <td>
                      {record.authorization_decision ? (
                        <span className={`badge ${getDecisionColor(record.authorization_decision)}`}>
                          {record.authorization_decision.toUpperCase()}
                        </span>
                      ) : (
                        <span className="text-muted small">-</span>
                      )}
                    </td>
                  </tr>
                  <tr>
                    <td className="text-muted small">Reason Code</td>
                    <td className="small">{record.reason_code || '-'}</td>
                  </tr>
                  <tr>
                    <td className="text-muted small">Policy ID</td>
                    <td className="small font-monospace">{record.policy_id || '-'}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="row">
            <div className="col-12">
              <h6 className="text-light border-bottom border-secondary pb-2"><i className="bi bi-braces me-2"></i>Context Snapshots</h6>
              
              <div className="accordion accordion-flush bg-transparent" id="snapshotsAccordion">
                {record.trust_snapshot && Object.keys(record.trust_snapshot).length > 0 && (
                  <div className="accordion-item bg-transparent border-secondary">
                    <h2 className="accordion-header">
                      <button className="accordion-button bg-black text-light border-secondary collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#trustSnapshot">
                        Trust Snapshot
                      </button>
                    </h2>
                    <div id="trustSnapshot" className="accordion-collapse collapse" data-bs-parent="#snapshotsAccordion">
                      <div className="accordion-body p-0 pt-2">
                        <pre className="bg-darker p-3 rounded border border-secondary text-info small overflow-auto mb-0" style={{ maxHeight: '200px' }}>
                          {JSON.stringify(record.trust_snapshot, null, 2)}
                        </pre>
                      </div>
                    </div>
                  </div>
                )}
                
                {record.evidence_snapshot && Object.keys(record.evidence_snapshot).length > 0 && (
                  <div className="accordion-item bg-transparent border-secondary">
                    <h2 className="accordion-header">
                      <button className="accordion-button bg-black text-light border-secondary collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#evidenceSnapshot">
                        Evidence Snapshot
                      </button>
                    </h2>
                    <div id="evidenceSnapshot" className="accordion-collapse collapse" data-bs-parent="#snapshotsAccordion">
                      <div className="accordion-body p-0 pt-2">
                        <pre className="bg-darker p-3 rounded border border-secondary text-warning small overflow-auto mb-0" style={{ maxHeight: '200px' }}>
                          {JSON.stringify(record.evidence_snapshot, null, 2)}
                        </pre>
                      </div>
                    </div>
                  </div>
                )}

                {record.event_metadata && Object.keys(record.event_metadata).length > 0 && (
                  <div className="accordion-item bg-transparent border-secondary">
                    <h2 className="accordion-header">
                      <button className="accordion-button bg-black text-light border-secondary collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#metadataSnapshot">
                        Event Metadata
                      </button>
                    </h2>
                    <div id="metadataSnapshot" className="accordion-collapse collapse" data-bs-parent="#snapshotsAccordion">
                      <div className="accordion-body p-0 pt-2">
                        <pre className="bg-darker p-3 rounded border border-secondary text-light small overflow-auto mb-0" style={{ maxHeight: '200px' }}>
                          {JSON.stringify(record.event_metadata, null, 2)}
                        </pre>
                      </div>
                    </div>
                  </div>
                )}
              </div>
              
              {(!record.trust_snapshot || Object.keys(record.trust_snapshot).length === 0) &&
               (!record.evidence_snapshot || Object.keys(record.evidence_snapshot).length === 0) &&
               (!record.event_metadata || Object.keys(record.event_metadata).length === 0) && (
                <div className="text-muted small fst-italic">No snapshot data available for this event.</div>
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

export const Audit = () => {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Filtering states
  const [searchTerm, setSearchTerm] = useState('');
  const [decisionFilter, setDecisionFilter] = useState('All');
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [typeFilter, setTypeFilter] = useState('All');
  
  // Modal state
  const [selectedRecord, setSelectedRecord] = useState(null);

  useEffect(() => {
    let isMounted = true;
    const fetchRecords = async () => {
      try {
        setLoading(true);
        const data = await auditApi.getAuditRecords(500); // Request more records to have a good dataset to filter
        if (isMounted) {
          // Sort chronologically (newest first)
          const sorted = data.sort((a, b) => new Date(b.occurred_at) - new Date(a.occurred_at));
          setRecords(sorted);
          setError(null);
        }
      } catch (err) {
        if (isMounted) {
          if (!err.response) {
            setError({ type: 'network', message: 'Backend Offline: Cannot connect to audit service.' });
          } else if (err.response.status === 401 || err.response.status === 403) {
            setError({ type: 'auth', message: 'Authentication required to view audit records.' });
          } else {
            setError({ type: 'api', message: `Error ${err.response.status}: Failed to fetch audit records` });
          }
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchRecords();
    return () => { isMounted = false; };
  }, []);

  // Derived stats
  const totalEvents = records.length;
  const authorizedEvents = records.filter(r => {
    const d = r.authorization_decision?.toLowerCase() || '';
    return d.includes('allow') || d.includes('success') || d.includes('permit');
  }).length;
  const deniedEvents = records.filter(r => {
    const d = r.authorization_decision?.toLowerCase() || '';
    return d.includes('deny') || d.includes('fail') || d.includes('reject');
  }).length;
  const securityEvents = records.filter(r => {
    const c = r.event_category?.toLowerCase() || '';
    return c === 'security' || c === 'authentication';
  }).length;

  const uniqueDecisions = ['All', ...new Set(records.map(r => r.authorization_decision).filter(Boolean))];
  const uniqueCategories = ['All', ...new Set(records.map(r => r.event_category).filter(Boolean))];
  const uniqueTypes = ['All', ...new Set(records.map(r => r.event_type).filter(Boolean))];

  // Filtering logic
  const filteredRecords = useMemo(() => {
    return records.filter(record => {
      const lowerSearch = searchTerm.toLowerCase();
      
      const matchesSearch = 
        record.event_type?.toLowerCase().includes(lowerSearch) ||
        record.event_category?.toLowerCase().includes(lowerSearch) ||
        record.actor_did?.toLowerCase().includes(lowerSearch) ||
        record.actor_organization_id?.toLowerCase().includes(lowerSearch) ||
        record.subject_agent_id?.toLowerCase().includes(lowerSearch) ||
        record.resource_type?.toLowerCase().includes(lowerSearch) ||
        record.resource_id?.toLowerCase().includes(lowerSearch) ||
        record.action_requested?.toLowerCase().includes(lowerSearch) ||
        record.reason_code?.toLowerCase().includes(lowerSearch) ||
        record.policy_id?.toLowerCase().includes(lowerSearch) ||
        record.correlation_id?.toLowerCase().includes(lowerSearch) ||
        record.id.toLowerCase().includes(lowerSearch);
        
      const matchesDecision = decisionFilter === 'All' || record.authorization_decision === decisionFilter;
      const matchesCategory = categoryFilter === 'All' || record.event_category === categoryFilter;
      const matchesType = typeFilter === 'All' || record.event_type === typeFilter;
      
      return matchesSearch && matchesDecision && matchesCategory && matchesType;
    });
  }, [records, searchTerm, decisionFilter, categoryFilter, typeFilter]);

  const getDecisionColor = (decision) => {
    if (!decision) return 'bg-secondary';
    const lower = decision.toLowerCase();
    if (lower.includes('allow') || lower.includes('success') || lower.includes('permit')) return 'bg-success';
    if (lower.includes('deny') || lower.includes('fail') || lower.includes('reject')) return 'bg-danger';
    return 'bg-secondary';
  };

  return (
    <div className="container-fluid position-relative">
      <style>{`
        .bg-darker { background-color: #1a1d20 !important; }
        .table-hover tbody tr:hover { background-color: rgba(255, 255, 255, 0.05); }
        .text-truncate-uuid { max-width: 150px; display: inline-block; vertical-align: middle; }
        /* Fix for accordion in dark mode */
        .accordion-button:not(.collapsed) { background-color: #212529; color: #fff; box-shadow: inset 0 -1px 0 rgba(255,255,255,.125); }
        .accordion-button::after { filter: invert(1) grayscale(100%) brightness(200%); }
      `}</style>
      
      <div className="row mb-4">
        <div className="col-12">
          <h2 className="mb-1 fw-bold">Audit & Traceability</h2>
          <p className="text-muted fs-6 mb-0">Chronological security and authorization events recorded by the trust framework.</p>
        </div>
      </div>
      
      {loading ? (
        <LoadingState message="Retrieving authoritative audit records..." />
      ) : error ? (
        <div className="card bg-dark border-secondary text-center p-5 shadow-sm">
          <i className="bi bi-exclamation-triangle text-warning fs-1 mb-3"></i>
          <p className={`mb-0 ${error.type === 'network' ? 'text-danger' : 'text-warning'}`}>{error.message}</p>
        </div>
      ) : records.length === 0 ? (
        <div className="card bg-dark border-secondary text-center p-5 shadow-sm">
          <i className="bi bi-journal-x text-muted fs-1 mb-3"></i>
          <p className="text-muted mb-0">No audit events exist.</p>
        </div>
      ) : (
        <>
          <div className="row mb-4">
            <div className="col-md-3">
              <StatCard title="Total Events" value={totalEvents} icon="journal-text" />
            </div>
            <div className="col-md-3">
              <StatCard title="Authorized" value={authorizedEvents} icon="shield-check" />
            </div>
            <div className="col-md-3">
              <StatCard title="Denied" value={deniedEvents} icon="shield-x" />
            </div>
            <div className="col-md-3">
              <StatCard title="Auth / Security" value={securityEvents} icon="shield-lock" />
            </div>
          </div>

          <div className="card bg-dark border-secondary shadow-sm">
            <div className="card-header border-secondary bg-transparent py-3">
              <div className="d-flex flex-column flex-xl-row justify-content-between align-items-xl-center gap-3">
                <h6 className="mb-0 fw-semibold text-light"><i className="bi bi-list-columns-reverse me-2"></i>Audit Trail</h6>
                <div className="d-flex flex-wrap gap-2">
                  <div className="input-group input-group-sm" style={{ width: '250px' }}>
                    <span className="input-group-text bg-dark border-secondary text-muted"><i className="bi bi-search"></i></span>
                    <input 
                      type="text" 
                      className="form-control bg-dark border-secondary text-light" 
                      placeholder="Search events..." 
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                    />
                  </div>
                  <select 
                    className="form-select form-select-sm bg-dark border-secondary text-light" 
                    style={{ width: '150px' }}
                    value={categoryFilter}
                    onChange={(e) => setCategoryFilter(e.target.value)}
                    title="Event Category"
                  >
                    <option value="All">All Categories</option>
                    {uniqueCategories.filter(c => c !== 'All').map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <select 
                    className="form-select form-select-sm bg-dark border-secondary text-light" 
                    style={{ width: '150px' }}
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                    title="Event Type"
                  >
                    <option value="All">All Types</option>
                    {uniqueTypes.filter(c => c !== 'All').map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <select 
                    className="form-select form-select-sm bg-dark border-secondary text-light" 
                    style={{ width: '150px' }}
                    value={decisionFilter}
                    onChange={(e) => setDecisionFilter(e.target.value)}
                    title="Authorization Decision"
                  >
                    <option value="All">All Decisions</option>
                    {uniqueDecisions.filter(c => c !== 'All').map(c => (
                      <option key={c} value={c}>{c.toUpperCase()}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
            
            <div className="card-body p-0">
              {filteredRecords.length === 0 ? (
                <div className="text-center p-5">
                  <i className="bi bi-search text-muted fs-1 mb-3 d-block"></i>
                  <p className="text-muted mb-0">No events match your filter criteria.</p>
                </div>
              ) : (
                <div className="table-responsive">
                  <table className="table table-dark table-hover mb-0 align-middle">
                    <thead>
                      <tr>
                        <th className="border-secondary px-3 py-3">Time</th>
                        <th className="border-secondary py-3">Event</th>
                        <th className="border-secondary py-3">Actor</th>
                        <th className="border-secondary py-3">Resource / Action</th>
                        <th className="border-secondary py-3">Decision</th>
                        <th className="border-secondary px-3 py-3 text-end">Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredRecords.map(record => (
                        <tr key={record.id}>
                          <td className="border-secondary px-3 text-muted small">
                            <div className="text-light">{new Date(record.occurred_at).toLocaleDateString()}</div>
                            <div>{new Date(record.occurred_at).toLocaleTimeString()}</div>
                          </td>
                          <td className="border-secondary">
                            <div className="text-light fw-semibold small">{record.event_type}</div>
                            <span className="badge bg-dark border border-secondary text-muted mt-1">{record.event_category}</span>
                          </td>
                          <td className="border-secondary">
                            <span className="font-monospace text-muted small text-truncate-uuid text-truncate" title={record.actor_did || record.actor_organization_id || 'System'}>
                              {record.actor_did || record.actor_organization_id || 'System'}
                            </span>
                          </td>
                          <td className="border-secondary">
                            {record.resource_type || record.action_requested ? (
                              <>
                                <div className="text-light small">{record.action_requested || record.resource_type}</div>
                                {record.resource_id && (
                                  <div className="font-monospace text-muted small text-truncate-uuid text-truncate mt-1" title={record.resource_id}>
                                    {record.resource_id}
                                  </div>
                                )}
                              </>
                            ) : (
                              <span className="text-muted small">-</span>
                            )}
                          </td>
                          <td className="border-secondary">
                            {record.authorization_decision ? (
                              <div>
                                <span className={`badge ${getDecisionColor(record.authorization_decision)}`}>
                                  {record.authorization_decision.toUpperCase()}
                                </span>
                                {record.reason_code && (
                                  <div className="text-muted small mt-1 text-truncate" style={{maxWidth: '150px'}} title={record.reason_code}>
                                    {record.reason_code}
                                  </div>
                                )}
                              </div>
                            ) : (
                              <span className="text-muted small">-</span>
                            )}
                          </td>
                          <td className="border-secondary px-3 text-end">
                            <button 
                              className="btn btn-sm btn-outline-light" 
                              onClick={() => setSelectedRecord(record)}
                            >
                              Inspect
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="card-footer border-secondary text-muted small text-end bg-transparent py-2">
              Showing {filteredRecords.length} of {records.length} total events
            </div>
          </div>
        </>
      )}

      {selectedRecord && (
        <AuditEventModal 
          record={selectedRecord} 
          onClose={() => setSelectedRecord(null)} 
        />
      )}
    </div>
  );
};
