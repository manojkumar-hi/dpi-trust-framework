import React, { useState, useEffect } from 'react';
import { delegationsApi } from '../api/delegations';
import { LoadingState } from '../components/common/LoadingState';
import { StatusBadge } from '../components/common/StatusBadge';

export const Delegations = () => {
  const [delegations, setDelegations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedCaps, setSelectedCaps] = useState(null);

  useEffect(() => {
    let isMounted = true;
    
    const fetchDelegations = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await delegationsApi.getDelegations();
        if (isMounted) {
          setDelegations(data);
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
  }, []);

  return (
    <div className="container-fluid relative">
      <div className="row mb-4">
        <div className="col-12">
          <h2>Delegations</h2>
          <p className="text-muted">Cryptographic delegations of authority within the trust framework.</p>
        </div>
      </div>
      
      {loading ? (
        <LoadingState message="Loading delegation registry..." />
      ) : error ? (
        <div className="card bg-dark border-secondary text-center p-5">
          <i className="bi bi-exclamation-triangle text-warning fs-1 mb-3"></i>
          <p className={`mb-0 ${error.type === 'network' ? 'text-danger' : 'text-warning'}`}>{error.message}</p>
        </div>
      ) : delegations.length === 0 ? (
        <div className="card bg-dark border-secondary text-center p-5">
          <i className="bi bi-diagram-3 text-muted fs-1 mb-3"></i>
          <p className="text-muted mb-0">No delegations found in the registry.</p>
        </div>
      ) : (
        <div className="card bg-dark border-secondary">
          <div className="table-responsive">
            <table className="table table-dark table-hover mb-0">
              <thead>
                <tr>
                  <th className="border-secondary">ID & Purpose</th>
                  <th className="border-secondary">Delegator</th>
                  <th className="border-secondary">Delegatee</th>
                  <th className="border-secondary">Capabilities</th>
                  <th className="border-secondary">Status</th>
                  <th className="border-secondary">Valid From / To</th>
                </tr>
              </thead>
              <tbody>
                {delegations.map(del => (
                  <tr key={del.id}>
                    <td className="border-secondary align-middle">
                      <div><strong className="text-light">{del.purpose}</strong></div>
                      <div className="text-muted font-monospace small">ID: {del.id}</div>
                      {del.parent_delegation_id && (
                        <div className="text-info font-monospace small mt-1">
                          <i className="bi bi-arrow-return-right me-1"></i>
                          Parent: {del.parent_delegation_id}
                        </div>
                      )}
                    </td>
                    <td className="border-secondary align-middle text-muted font-monospace small" title={del.delegator_organization_id}>
                      {del.delegator_did || del.delegator_organization_id}
                    </td>
                    <td className="border-secondary align-middle text-muted font-monospace small" title={del.delegatee_agent_id}>
                      {del.delegatee_did || del.delegatee_agent_id}
                    </td>
                    <td className="border-secondary align-middle">
                      {del.capabilities?.map((cap, idx) => (
                        <div key={idx} className="mb-1 d-flex align-items-center">
                          <span className="badge bg-secondary me-2">{cap.capability_code}</span>
                          {(Object.keys(cap.scope || {}).length > 0 || Object.keys(cap.constraints || {}).length > 0) && (
                            <button 
                              className="btn btn-sm btn-link text-info p-0 ms-1" 
                              title="View Scope & Constraints"
                              onClick={() => setSelectedCaps(del.capabilities)}
                            >
                              <i className="bi bi-info-circle"></i>
                            </button>
                          )}
                        </div>
                      ))}
                    </td>
                    <td className="border-secondary align-middle"><StatusBadge status={del.status} /></td>
                    <td className="border-secondary align-middle text-muted small">
                      <div><i className="bi bi-calendar-check me-1"></i> {new Date(del.starts_at).toLocaleDateString()}</div>
                      <div><i className="bi bi-calendar-x me-1"></i> {new Date(del.expires_at).toLocaleDateString()}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedCaps && (
        <>
          <div className="modal-backdrop fade show" style={{ opacity: 0.5 }}></div>
          <div className="modal d-block" tabIndex="-1" role="dialog" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
            <div className="modal-dialog modal-lg modal-dialog-centered" role="document">
              <div className="modal-content bg-dark border-secondary shadow-lg">
                <div className="modal-header border-secondary">
                  <h5 className="modal-title d-flex align-items-center">
                    <i className="bi bi-list-check text-info me-2"></i>
                    Delegation Capabilities & Constraints
                  </h5>
                  <button type="button" className="btn-close btn-close-white" aria-label="Close" onClick={() => setSelectedCaps(null)}></button>
                </div>
                <div className="modal-body p-0">
                  <ul className="list-group list-group-flush bg-transparent">
                    {selectedCaps.map((cap, idx) => (
                      <li key={idx} className="list-group-item bg-transparent text-light border-secondary p-4">
                        <h6 className="text-primary mb-3">Capability: <span className="text-light">{cap.capability_code}</span></h6>
                        
                        <div className="row">
                          <div className="col-md-6 mb-3 mb-md-0">
                            <strong className="d-block mb-2 text-muted">Scope</strong>
                            {Object.keys(cap.scope || {}).length > 0 ? (
                              <pre className="bg-black p-3 rounded border border-secondary text-info mb-0" style={{ fontSize: '0.85rem' }}>
                                {JSON.stringify(cap.scope, null, 2)}
                              </pre>
                            ) : (
                              <span className="text-muted small">No specific scope defined (Global).</span>
                            )}
                          </div>
                          <div className="col-md-6">
                            <strong className="d-block mb-2 text-muted">Constraints</strong>
                            {Object.keys(cap.constraints || {}).length > 0 ? (
                              <pre className="bg-black p-3 rounded border border-secondary text-warning mb-0" style={{ fontSize: '0.85rem' }}>
                                {JSON.stringify(cap.constraints, null, 2)}
                              </pre>
                            ) : (
                              <span className="text-muted small">No constraints applied.</span>
                            )}
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="modal-footer border-secondary">
                  <button type="button" className="btn btn-secondary" onClick={() => setSelectedCaps(null)}>Close</button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
