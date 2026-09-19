import React, { useState, useEffect, useMemo, useRef } from 'react';
import { credentialsApi } from '../api/credentials';
import { verificationApi } from '../api/verification';
import { LoadingState } from '../components/common/LoadingState';
import { StatusBadge } from '../components/common/StatusBadge';
import { StatCard } from '../components/common/StatCard';

const CredentialDetailsModal = ({ credential, onClose }) => {
  const [verifyResult, setVerifyResult] = useState(null);
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [verifyError, setVerifyError] = useState(null);
  const [showJwt, setShowJwt] = useState(false);
  const [copied, setCopied] = useState(false);
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
    if (!credential.vc_jwt) return;
    
    try {
      setVerifyLoading(true);
      setVerifyError(null);
      const data = await verificationApi.verifyVC(credential.vc_jwt);
      setVerifyResult(data);
    } catch (err) {
      if (!err.response) {
        setVerifyError('Backend Offline: Cannot reach verification service');
      } else {
        setVerifyError(`Verification Error (${err.response.status}): ${err.response.data?.detail || 'Failed to verify'}`);
      }
    } finally {
      setVerifyLoading(false);
    }
  };

  const handleCopyJwt = () => {
    if (credential.vc_jwt) {
      navigator.clipboard.writeText(credential.vc_jwt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!credential) return null;

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
      <div className="card bg-dark border-secondary shadow-lg w-100" style={{ maxWidth: '800px', maxHeight: '95vh', overflowY: 'auto' }}>
        <div className="card-header border-secondary d-flex justify-content-between align-items-center bg-transparent py-3">
          <h5 className="mb-0 text-light" id="modal-title">
            <i className="bi bi-card-heading me-2 text-primary"></i>
            Credential Details
          </h5>
          <button className="btn-close btn-close-white" onClick={onClose} aria-label="Close"></button>
        </div>
        <div className="card-body">
          <div className="row mb-4">
            <div className="col-12 col-md-6 mb-3 mb-md-0">
              <h6 className="text-light border-bottom border-secondary pb-2"><i className="bi bi-fingerprint me-2"></i>Identity</h6>
              <table className="table table-dark table-sm table-borderless mb-0">
                <tbody>
                  <tr>
                    <td className="text-muted w-25">ID</td>
                    <td className="font-monospace small text-truncate" style={{maxWidth: '200px'}} title={credential.id}>{credential.id}</td>
                  </tr>
                  <tr>
                    <td className="text-muted">Type</td>
                    <td><span className="badge bg-primary bg-opacity-25 text-primary border border-primary">{credential.credential_type}</span></td>
                  </tr>
                  <tr>
                    <td className="text-muted">Issuer</td>
                    <td className="font-monospace small text-truncate" style={{maxWidth: '200px'}} title={credential.issuer_organization_id}>{credential.issuer_organization_id}</td>
                  </tr>
                  <tr>
                    <td className="text-muted">Subject</td>
                    <td className="font-monospace small text-truncate" style={{maxWidth: '200px'}} title={credential.subject_agent_id}>{credential.subject_agent_id}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            
            <div className="col-12 col-md-6">
              <h6 className="text-light border-bottom border-secondary pb-2"><i className="bi bi-clock-history me-2"></i>Lifecycle</h6>
              <table className="table table-dark table-sm table-borderless mb-0">
                <tbody>
                  <tr>
                    <td className="text-muted w-25">Status</td>
                    <td><StatusBadge status={credential.status} /></td>
                  </tr>
                  <tr>
                    <td className="text-muted">Issued</td>
                    <td className="small">{new Date(credential.issued_at).toLocaleString()}</td>
                  </tr>
                  <tr>
                    <td className="text-muted">Expires</td>
                    <td className="small">{credential.expires_at ? new Date(credential.expires_at).toLocaleString() : 'Never'}</td>
                  </tr>
                  {credential.revoked_at && (
                    <>
                      <tr>
                        <td className="text-muted text-danger">Revoked</td>
                        <td className="small text-danger">{new Date(credential.revoked_at).toLocaleString()}</td>
                      </tr>
                      <tr>
                        <td className="text-muted">Reason</td>
                        <td className="small">{credential.revocation_reason}</td>
                      </tr>
                    </>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="row mb-4">
            <div className="col-12">
              <h6 className="text-light border-bottom border-secondary pb-2"><i className="bi bi-shield-lock me-2"></i>Cryptographic Metadata</h6>
              <table className="table table-dark table-sm table-borderless mb-0">
                <tbody>
                  <tr>
                    <td className="text-muted" style={{width: '150px'}}>Proof Type</td>
                    <td className="small">{credential.proof_type || 'N/A'}</td>
                  </tr>
                  <tr>
                    <td className="text-muted">Key ID (kid)</td>
                    <td className="font-monospace small">{credential.kid || 'N/A'}</td>
                  </tr>
                  <tr>
                    <td className="text-muted">Signed At</td>
                    <td className="small">{credential.signed_at ? new Date(credential.signed_at).toLocaleString() : 'N/A'}</td>
                  </tr>
                  <tr>
                    <td className="text-muted">Fabric TX ID</td>
                    <td className="font-monospace small text-truncate" style={{maxWidth: '400px'}} title={credential.transaction_id}>{credential.transaction_id || 'N/A'}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {credential.vc_jwt ? (
            <div className="card bg-darker border-secondary mb-4 shadow-sm">
              <div className="card-header border-secondary bg-transparent d-flex justify-content-between align-items-center">
                <h6 className="mb-0 text-light"><i className="bi bi-check2-circle me-2"></i>Verification</h6>
                <div>
                  <button className="btn btn-sm btn-outline-info me-2" onClick={() => setShowJwt(!showJwt)}>
                    {showJwt ? 'Hide VC JWT' : 'View VC JWT'}
                  </button>
                  <button className="btn btn-sm btn-primary" onClick={handleVerify} disabled={verifyLoading}>
                    {verifyLoading ? <span className="spinner-border spinner-border-sm" role="status"></span> : 'Verify Credential'}
                  </button>
                </div>
              </div>
              
              {showJwt && (
                <div className="card-body border-bottom border-secondary bg-black p-3 position-relative">
                  <button 
                    className="btn btn-sm btn-outline-secondary position-absolute top-0 end-0 m-2" 
                    onClick={handleCopyJwt}
                    title="Copy JWT"
                  >
                    {copied ? <i className="bi bi-check text-success"></i> : <i className="bi bi-clipboard"></i>}
                  </button>
                  <p className="text-muted small mb-2">Stateless JWT Artifact</p>
                  <pre className="text-light font-monospace small mb-0 pe-5" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: '0.75rem', maxHeight: '150px', overflowY: 'auto' }}>
                    {credential.vc_jwt}
                  </pre>
                </div>
              )}

              {verifyError && (
                <div className="card-body bg-danger bg-opacity-10">
                  <div className="text-danger small"><i className="bi bi-exclamation-triangle me-2"></i>{verifyError}</div>
                </div>
              )}

              {verifyResult && (
                <div className="card-body">
                  <div className="row">
                    <div className="col-md-6 border-end border-secondary">
                      <h6 className="text-light mb-3">Cryptographic Verification</h6>
                      <div className="d-flex align-items-center mb-2">
                        <i className={`bi fs-4 me-3 ${verifyResult.valid ? 'bi-shield-check text-success' : 'bi-shield-x text-danger'}`}></i>
                        <div>
                          <div className={`fw-bold ${verifyResult.valid ? 'text-success' : 'text-danger'}`}>
                            {verifyResult.valid ? 'Valid Signature' : 'Invalid Signature'}
                          </div>
                          <div className="text-muted small">{verifyResult.reason_code || 'Signature cryptographic check'}</div>
                        </div>
                      </div>
                      <div className="mt-3">
                        <div className="text-muted small">Signature Status</div>
                        <div className="text-light small">{verifyResult.signature_status || 'Unknown'}</div>
                      </div>
                    </div>
                    <div className="col-md-6 ps-md-4">
                      <h6 className="text-light mb-3">Local Registry Status</h6>
                      <div className="mb-2">
                        <div className="text-muted small">Current Local Status</div>
                        <div>
                          <StatusBadge status={verifyResult.local_status} />
                        </div>
                      </div>
                      <div className="mt-3">
                        <div className="text-muted small">Issuer DID</div>
                        <div className="font-monospace small text-light text-truncate" title={verifyResult.issuer_did}>{verifyResult.issuer_did || 'N/A'}</div>
                      </div>
                      <div className="mt-2">
                        <div className="text-muted small">Subject DID</div>
                        <div className="font-monospace small text-light text-truncate" title={verifyResult.subject_did}>{verifyResult.subject_did || 'N/A'}</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="alert alert-secondary bg-dark border-secondary text-muted small py-2 d-flex align-items-center mb-4 shadow-sm">
              <i className="bi bi-info-circle me-3 fs-4"></i>
              <div>
                <strong>Verification Unavailable:</strong> This credential does not have a locally stored VC JWT artifact for stateless verification.
              </div>
            </div>
          )}

          {credential.credential_data && (
            <div className="card bg-black border-secondary">
              <div className="card-header border-secondary bg-transparent py-2">
                <span className="text-muted small">Credential Data</span>
              </div>
              <div className="card-body p-0">
                <pre className="text-info font-monospace small mb-0 p-3" style={{ maxHeight: '200px', overflowY: 'auto' }}>
                  {typeof credential.credential_data === 'object' 
                    ? JSON.stringify(credential.credential_data, null, 2) 
                    : credential.credential_data}
                </pre>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};

export const Credentials = () => {
  const [credentials, setCredentials] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Filtering states
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  
  // Modal state
  const [selectedCred, setSelectedCred] = useState(null);

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

  // Derived stats
  const totalCreds = credentials.length;
  const activeCreds = credentials.filter(c => c.status === 'active').length;
  const revokedCreds = credentials.filter(c => c.status === 'revoked').length;
  const expiredCreds = credentials.filter(c => c.status === 'expired').length;

  const uniqueStatuses = ['All', ...new Set(credentials.map(c => c.status))];

  // Filtering logic
  const filteredCredentials = useMemo(() => {
    return credentials.filter(cred => {
      const lowerSearch = searchTerm.toLowerCase();
      const matchesSearch = 
        cred.id.toLowerCase().includes(lowerSearch) || 
        cred.credential_type.toLowerCase().includes(lowerSearch) ||
        cred.issuer_organization_id.toLowerCase().includes(lowerSearch) ||
        cred.subject_agent_id.toLowerCase().includes(lowerSearch);
        
      const matchesStatus = statusFilter === 'All' || cred.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [credentials, searchTerm, statusFilter]);

  return (
    <div className="container-fluid position-relative">
      <style>{`
        .bg-darker { background-color: #1a1d20 !important; }
        .table-hover tbody tr:hover { background-color: rgba(255, 255, 255, 0.05); }
        .text-truncate-uuid { max-width: 120px; display: inline-block; vertical-align: middle; }
      `}</style>
      
      <div className="row mb-4">
        <div className="col-12">
          <h2 className="mb-1 fw-bold">Credential Registry</h2>
          <p className="text-muted fs-6">Verifiable credentials issued within the trust framework.</p>
        </div>
      </div>
      
      {loading ? (
        <LoadingState message="Loading credential registry..." />
      ) : error ? (
        <div className="card bg-dark border-secondary text-center p-5 shadow-sm">
          <i className="bi bi-exclamation-triangle text-warning fs-1 mb-3"></i>
          <p className={`mb-0 ${error.type === 'network' ? 'text-danger' : 'text-warning'}`}>{error.message}</p>
        </div>
      ) : (
        <>
          <div className="row mb-4">
            <div className="col-md-3">
              <StatCard title="Total Credentials" value={totalCreds} icon="card-heading" />
            </div>
            <div className="col-md-3">
              <StatCard title="Active" value={activeCreds} icon="check-circle" />
            </div>
            <div className="col-md-3">
              <StatCard title="Revoked" value={revokedCreds} icon="slash-circle" />
            </div>
            <div className="col-md-3">
              <StatCard title="Expired" value={expiredCreds} icon="clock-history" />
            </div>
          </div>

          <div className="card bg-dark border-secondary shadow-sm">
            <div className="card-header border-secondary bg-transparent py-3 d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3">
              <h6 className="mb-0 fw-semibold text-light"><i className="bi bi-list-ul me-2"></i>Issued Credentials</h6>
              <div className="d-flex flex-column flex-md-row gap-2">
                <div className="input-group input-group-sm" style={{ width: '300px' }}>
                  <span className="input-group-text bg-dark border-secondary text-muted"><i className="bi bi-search"></i></span>
                  <input 
                    type="text" 
                    className="form-control bg-dark border-secondary text-light" 
                    placeholder="Search ID, Type, Issuer, Subject..." 
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
              {filteredCredentials.length === 0 ? (
                <div className="text-center p-5">
                  <i className="bi bi-search text-muted fs-1 mb-3 d-block"></i>
                  <p className="text-muted mb-0">No credentials match your search criteria.</p>
                </div>
              ) : (
                <div className="table-responsive">
                  <table className="table table-dark table-hover mb-0 align-middle text-nowrap">
                    <thead>
                      <tr>
                        <th className="border-secondary px-3 py-3">Credential ID</th>
                        <th className="border-secondary py-3">Type</th>
                        <th className="border-secondary py-3">Issuer</th>
                        <th className="border-secondary py-3">Subject Agent</th>
                        <th className="border-secondary py-3">Status</th>
                        <th className="border-secondary py-3">Issued / Expires</th>
                        <th className="border-secondary px-3 py-3 text-end">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredCredentials.map(cred => (
                        <tr key={cred.id}>
                          <td className="border-secondary px-3">
                            <span className="font-monospace text-muted small text-truncate-uuid text-truncate" title={cred.id}>{cred.id}</span>
                          </td>
                          <td className="border-secondary">
                            <span className="text-light">{cred.credential_type}</span>
                          </td>
                          <td className="border-secondary">
                            <span className="font-monospace text-muted small text-truncate-uuid text-truncate" title={cred.issuer_organization_id}>{cred.issuer_organization_id}</span>
                          </td>
                          <td className="border-secondary">
                            <span className="font-monospace text-muted small text-truncate-uuid text-truncate" title={cred.subject_agent_id}>{cred.subject_agent_id}</span>
                          </td>
                          <td className="border-secondary"><StatusBadge status={cred.status} /></td>
                          <td className="border-secondary text-muted small">
                            <div><i className="bi bi-calendar me-1"></i> {new Date(cred.issued_at).toLocaleDateString()}</div>
                            <div className={cred.expires_at && new Date(cred.expires_at) < new Date() ? 'text-danger' : ''}>
                              <i className="bi bi-clock me-1"></i> {cred.expires_at ? new Date(cred.expires_at).toLocaleDateString() : 'Never'}
                            </div>
                          </td>
                          <td className="border-secondary px-3 text-end">
                            <button 
                              className="btn btn-sm btn-outline-light" 
                              onClick={() => setSelectedCred(cred)}
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

      {selectedCred && (
        <CredentialDetailsModal 
          credential={selectedCred} 
          onClose={() => setSelectedCred(null)} 
        />
      )}
    </div>
  );
};
