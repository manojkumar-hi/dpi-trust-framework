import React, { useState, useEffect } from 'react';
import { auditApi } from '../api/audit';
import { LoadingState } from '../components/common/LoadingState';

export const Audit = () => {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedRecord, setSelectedRecord] = useState(null);

  useEffect(() => {
    const fetchRecords = async () => {
      try {
        setLoading(true);
        const data = await auditApi.getAuditRecords();
        setRecords(data);
        setError(null);
      } catch (err) {
        if (!err.response) {
          setError({ type: 'network', message: 'Backend Offline: Cannot connect to audit service.' });
        } else if (err.response.status === 401 || err.response.status === 403) {
          setError({ type: 'auth', message: 'Authentication required to view audit records.' });
        } else {
          setError({ type: 'api', message: `Error ${err.response.status}: Failed to fetch audit records` });
        }
      } finally {
        setLoading(false);
      }
    };

    fetchRecords();
  }, []);

  if (loading) return <LoadingState message="Retrieving authoritative audit records..." />;

  const getDecisionColor = (decision) => {
    if (!decision) return 'bg-secondary';
    const lower = decision.toLowerCase();
    if (lower.includes('allow') || lower.includes('success')) return 'bg-success';
    if (lower.includes('deny') || lower.includes('fail') || lower.includes('reject')) return 'bg-danger';
    return 'bg-secondary';
  };

  return (
    <div className="container-fluid">
      <div className="row mb-4">
        <div className="col-12">
          <h2>Audit & Traceability</h2>
          <p className="text-muted">
            Read-only chronological trail of trust, authorization, and lifecycle events.
            <br />
            <small>
              <i className="bi bi-info-circle me-1"></i>
              These are authoritative PostgreSQL records. If Fabric transaction anchoring is enabled, standard correlation IDs may link these to the distributed ledger.
            </small>
          </p>
        </div>
      </div>

      {error ? (
        <div className="alert alert-dark border-danger text-danger d-flex align-items-center" role="alert">
          <i className="bi bi-exclamation-triangle-fill fs-4 me-3"></i>
          <div>
            <strong>Audit Retrieval Failed</strong>
            <div className="small mt-1">{error.message}</div>
          </div>
        </div>
      ) : records.length === 0 ? (
        <div className="card bg-dark border-secondary text-center p-5">
          <i className="bi bi-journal-x text-muted fs-1 mb-3"></i>
          <p className="text-muted mb-0">No audit records found.</p>
        </div>
      ) : (
        <div className="row">
          <div className="col-12">
            <div className="card bg-dark border-secondary">
              <div className="card-header border-secondary d-flex justify-content-between align-items-center">
                <h5 className="mb-0 text-light"><i className="bi bi-list-columns-reverse me-2"></i>Audit Trail</h5>
                <span className="badge bg-secondary">{records.length} records</span>
              </div>
              <div className="table-responsive">
                <table className="table table-dark table-hover mb-0 align-middle">
                  <thead>
                    <tr>
                      <th className="text-muted small border-secondary">Timestamp</th>
                      <th className="text-muted small border-secondary">Event</th>
                      <th className="text-muted small border-secondary">Actor</th>
                      <th className="text-muted small border-secondary">Resource</th>
                      <th className="text-muted small border-secondary">Decision</th>
                      <th className="text-muted small border-secondary text-end">Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map(record => (
                      <tr key={record.id}>
                        <td>
                          <div className="small text-light">
                            {new Date(record.occurred_at).toLocaleString()}
                          </div>
                          <div className="text-muted" style={{ fontSize: '0.7rem' }}>
                            {record.id.split('-')[0]}
                          </div>
                        </td>
                        <td>
                          <div className="text-light small fw-bold">{record.event_type}</div>
                          <div className="text-muted" style={{ fontSize: '0.75rem' }}>{record.event_category}</div>
                        </td>
                        <td>
                          <div className="font-monospace text-light text-truncate" style={{ maxWidth: '150px', fontSize: '0.75rem' }}>
                            {record.actor_did || 'Unknown DID'}
                          </div>
                        </td>
                        <td>
                          {record.resource_type ? (
                            <>
                              <div className="small text-light">{record.resource_type}</div>
                              <div className="text-muted font-monospace text-truncate" style={{ maxWidth: '150px', fontSize: '0.7rem' }}>
                                {record.resource_id}
                              </div>
                            </>
                          ) : (
                            <span className="text-muted small">-</span>
                          )}
                        </td>
                        <td>
                          {record.authorization_decision ? (
                            <span className={`badge ${getDecisionColor(record.authorization_decision)}`}>
                              {record.authorization_decision}
                            </span>
                          ) : (
                            <span className="text-muted small">-</span>
                          )}
                        </td>
                        <td className="text-end">
                          <button 
                            className="btn btn-sm btn-outline-secondary"
                            onClick={() => setSelectedRecord(record)}
                          >
                            <i className="bi bi-code-square"></i>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {selectedRecord && (
        <>
          <div className="modal-backdrop fade show"></div>
          <div className="modal fade show d-block" tabIndex="-1">
            <div className="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
              <div className="modal-content bg-dark border-secondary">
                <div className="modal-header border-secondary bg-black bg-opacity-25">
                  <h5 className="modal-title text-light">
                    <i className="bi bi-file-earmark-text text-primary me-2"></i>
                    Audit Record Details
                  </h5>
                  <button type="button" className="btn-close btn-close-white" onClick={() => setSelectedRecord(null)}></button>
                </div>
                <div className="modal-body">
                  <div className="row mb-3">
                    <div className="col-md-6">
                      <span className="text-muted d-block small">Record ID</span>
                      <span className="text-light font-monospace small">{selectedRecord.id}</span>
                    </div>
                    <div className="col-md-6">
                      <span className="text-muted d-block small">Timestamp</span>
                      <span className="text-light small">{new Date(selectedRecord.occurred_at).toLocaleString()}</span>
                    </div>
                  </div>
                  
                  <div className="row mb-3">
                    <div className="col-md-6">
                      <span className="text-muted d-block small">Event Category</span>
                      <span className="text-light small">{selectedRecord.event_category}</span>
                    </div>
                    <div className="col-md-6">
                      <span className="text-muted d-block small">Event Type</span>
                      <span className="text-light small">{selectedRecord.event_type}</span>
                    </div>
                  </div>

                  <div className="row mb-3">
                    <div className="col-md-6">
                      <span className="text-muted d-block small">Action Requested</span>
                      <span className="text-light small">{selectedRecord.action_requested || '-'}</span>
                    </div>
                    <div className="col-md-6">
                      <span className="text-muted d-block small">Correlation ID</span>
                      <span className="text-light font-monospace small">{selectedRecord.correlation_id || '-'}</span>
                    </div>
                  </div>

                  <div className="row mb-3">
                    <div className="col-md-6">
                      <span className="text-muted d-block small">Decision</span>
                      {selectedRecord.authorization_decision ? (
                        <span className={`badge ${getDecisionColor(selectedRecord.authorization_decision)}`}>
                          {selectedRecord.authorization_decision}
                        </span>
                      ) : (
                        <span className="text-light small">-</span>
                      )}
                    </div>
                    <div className="col-md-6">
                      <span className="text-muted d-block small">Reason Code</span>
                      <span className="text-light small">{selectedRecord.reason_code || '-'}</span>
                    </div>
                  </div>

                  <div className="mb-3 border-top border-secondary pt-3">
                    <span className="text-muted d-block small mb-1">Actor Identity</span>
                    <div className="bg-black p-2 rounded border border-secondary text-light font-monospace small" style={{ wordBreak: 'break-all' }}>
                      {selectedRecord.actor_did || 'System / Not Provided'}
                    </div>
                    {selectedRecord.actor_organization_id && (
                      <div className="mt-1 small">
                        <span className="text-muted me-2">Org ID:</span>
                        <span className="font-monospace text-light">{selectedRecord.actor_organization_id}</span>
                      </div>
                    )}
                  </div>

                  {selectedRecord.event_metadata && Object.keys(selectedRecord.event_metadata).length > 0 && (
                    <div className="mb-3 border-top border-secondary pt-3">
                      <span className="text-muted d-block small mb-2">Event Metadata</span>
                      <pre className="bg-black p-3 rounded border border-secondary text-light small overflow-auto">
                        {JSON.stringify(selectedRecord.event_metadata, null, 2)}
                      </pre>
                    </div>
                  )}

                  {selectedRecord.trust_snapshot && Object.keys(selectedRecord.trust_snapshot).length > 0 && (
                    <div className="mb-3 border-top border-secondary pt-3">
                      <span className="text-muted d-block small mb-2">Trust Snapshot (at time of event)</span>
                      <pre className="bg-black p-3 rounded border border-secondary text-light small overflow-auto">
                        {JSON.stringify(selectedRecord.trust_snapshot, null, 2)}
                      </pre>
                    </div>
                  )}
                  
                </div>
                <div className="modal-footer border-secondary">
                  <button type="button" className="btn btn-secondary" onClick={() => setSelectedRecord(null)}>Close</button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
