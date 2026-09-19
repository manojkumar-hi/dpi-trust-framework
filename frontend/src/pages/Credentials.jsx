import React, { useState, useEffect } from 'react';
import { credentialsApi } from '../api/credentials';
import { LoadingState } from '../components/common/LoadingState';
import { StatusBadge } from '../components/common/StatusBadge';

export const Credentials = () => {
  const [credentials, setCredentials] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedJwt, setSelectedJwt] = useState(null);

  useEffect(() => {
    let isMounted = true;
    
    const fetchCredentials = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await credentialsApi.getCredentials();
        if (isMounted) {
          setCredentials(data);
        }
      } catch (err) {
        if (isMounted) {
          if (!err.response) {
            setError({ type: 'network', message: 'Backend Offline: Cannot retrieve credentials' });
          } else if (err.response.status === 401 || err.response.status === 403) {
            setError({ type: 'auth', message: 'Authentication required to view credentials' });
          } else {
            setError({ type: 'api', message: `Error ${err.response.status}: Failed to load credentials` });
          }
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchCredentials();
    
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="container-fluid relative">
      <div className="row mb-4">
        <div className="col-12">
          <h2>Credentials</h2>
          <p className="text-muted">Verifiable Credentials issued to identities within the network.</p>
        </div>
      </div>
      
      {loading ? (
        <LoadingState message="Loading credential registry..." />
      ) : error ? (
        <div className="card bg-dark border-secondary text-center p-5">
          <i className="bi bi-exclamation-triangle text-warning fs-1 mb-3"></i>
          <p className={`mb-0 ${error.type === 'network' ? 'text-danger' : 'text-warning'}`}>{error.message}</p>
        </div>
      ) : credentials.length === 0 ? (
        <div className="card bg-dark border-secondary text-center p-5">
          <i className="bi bi-card-heading text-muted fs-1 mb-3"></i>
          <p className="text-muted mb-0">No credentials found in the registry.</p>
        </div>
      ) : (
        <div className="card bg-dark border-secondary">
          <div className="table-responsive">
            <table className="table table-dark table-hover mb-0">
              <thead>
                <tr>
                  <th className="border-secondary">Credential ID</th>
                  <th className="border-secondary">Type</th>
                  <th className="border-secondary">Subject Agent</th>
                  <th className="border-secondary">Issuer Org</th>
                  <th className="border-secondary">Status</th>
                  <th className="border-secondary">Issued / Expires</th>
                  <th className="border-secondary text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {credentials.map(cred => (
                  <tr key={cred.id}>
                    <td className="border-secondary align-middle text-muted font-monospace small">{cred.id}</td>
                    <td className="border-secondary align-middle">
                      <div className="d-flex align-items-center">
                        <i className="bi bi-shield-check me-2 text-primary"></i>
                        {cred.credential_type}
                      </div>
                      {cred.proof_type && <span className="badge bg-secondary mt-1">{cred.proof_type}</span>}
                    </td>
                    <td className="border-secondary align-middle text-muted font-monospace small">{cred.subject_agent_id}</td>
                    <td className="border-secondary align-middle text-muted font-monospace small">{cred.issuer_organization_id}</td>
                    <td className="border-secondary align-middle"><StatusBadge status={cred.status} /></td>
                    <td className="border-secondary align-middle text-muted small">
                      <div>Issued: {new Date(cred.issued_at).toLocaleDateString()}</div>
                      <div>{cred.expires_at ? `Expires: ${new Date(cred.expires_at).toLocaleDateString()}` : 'No expiry'}</div>
                    </td>
                    <td className="border-secondary align-middle text-center">
                      {cred.vc_jwt ? (
                        <button 
                          className="btn btn-sm btn-outline-info" 
                          onClick={() => setSelectedJwt(cred.vc_jwt)}
                          title="View VC JWT Artifact"
                        >
                          <i className="bi bi-code-slash"></i> View JWT
                        </button>
                      ) : (
                        <span className="text-muted small">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedJwt && (
        <>
          <div className="modal-backdrop fade show" style={{ opacity: 0.5 }}></div>
          <div className="modal d-block" tabIndex="-1" role="dialog" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
            <div className="modal-dialog modal-lg modal-dialog-centered" role="document">
              <div className="modal-content bg-dark border-secondary shadow-lg">
                <div className="modal-header border-secondary">
                  <h5 className="modal-title d-flex align-items-center">
                    <i className="bi bi-file-earmark-code text-info me-2"></i>
                    Verifiable Credential (JWT)
                  </h5>
                  <button type="button" className="btn-close btn-close-white" aria-label="Close" onClick={() => setSelectedJwt(null)}></button>
                </div>
                <div className="modal-body">
                  <p className="text-muted small mb-2">This is the cryptographically signed credential artifact.</p>
                  <textarea 
                    className="form-control bg-black text-light border-secondary font-monospace" 
                    rows="10" 
                    readOnly 
                    value={selectedJwt}
                    style={{ fontSize: '0.85rem' }}
                  ></textarea>
                </div>
                <div className="modal-footer border-secondary">
                  <button type="button" className="btn btn-secondary" onClick={() => setSelectedJwt(null)}>Close</button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
