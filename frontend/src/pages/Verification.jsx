import React, { useState } from 'react';
import { verificationApi } from '../api/verification';

export const Verification = () => {
  const [jwt, setJwt] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleVerify = async () => {
    const trimmedJwt = jwt.trim();
    if (!trimmedJwt) {
      setError({ type: 'validation', message: 'Enter a VC-JWT artifact.' });
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setResult(null);
      
      const data = await verificationApi.verifyVC(trimmedJwt);
      setResult(data);
    } catch (err) {
      if (!err.response) {
        setError({ type: 'network', message: 'Verification service unavailable.' });
      } else if (err.response.status === 400) {
        setError({ type: 'api', message: 'Verification request was rejected.' });
      } else if (err.response.status === 401 || err.response.status === 403) {
        setError({ type: 'auth', message: 'Authentication/authorization required.' });
      } else {
        setError({ type: 'api', message: `Error ${err.response.status}: Verification request failed.` });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setJwt('');
    setResult(null);
    setError(null);
  };

  const copyToClipboard = async (text, label) => {
    try {
      await navigator.clipboard.writeText(text);
      // Optional: Could add a small toast here if desired, but keeping it simple for now
    } catch (err) {
      console.error('Failed to copy', err);
    }
  };

  return (
    <div className="container-fluid relative">
      <div className="row mb-4">
        <div className="col-12">
          <h2 className="mb-1 fw-bold">Credential Verification</h2>
          <p className="text-muted fs-6 mb-0">Verify a Verifiable Credential artifact and inspect its cryptographic and local verification status.</p>
        </div>
      </div>
      
      <div className="row">
        <div className="col-lg-6 mb-4">
          <div className="card bg-dark border-secondary h-100 shadow-sm">
            <div className="card-header border-secondary d-flex justify-content-between align-items-center bg-transparent py-3">
              <h5 className="mb-0 text-light"><i className="bi bi-file-earmark-lock text-primary me-2"></i>Verifiable Credential JWT</h5>
            </div>
            <div className="card-body d-flex flex-column">
              <textarea 
                className="form-control bg-black text-light border-secondary font-monospace flex-grow-1 mb-4" 
                rows="12" 
                placeholder="Paste a VC-JWT artifact here..."
                value={jwt}
                onChange={(e) => setJwt(e.target.value)}
                style={{ fontSize: '0.85rem' }}
                disabled={loading}
              ></textarea>
              
              <div className="d-flex justify-content-between mt-auto">
                <button 
                  className="btn btn-outline-secondary px-4" 
                  onClick={handleClear}
                  disabled={loading || (!jwt && !result && !error)}
                >
                  <i className="bi bi-trash me-2"></i>Clear
                </button>
                <button 
                  className="btn btn-primary px-4" 
                  onClick={handleVerify}
                  disabled={loading || !jwt.trim()}
                >
                  {loading ? (
                    <><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Verifying...</>
                  ) : (
                    <><i className="bi bi-shield-check me-2"></i> Verify Credential</>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
        
        <div className="col-lg-6 mb-4">
          <div className="card bg-dark border-secondary h-100 shadow-sm">
            <div className="card-header border-secondary bg-transparent py-3">
              <h5 className="mb-0 text-light"><i className="bi bi-shield-shaded text-info me-2"></i>Verification Result</h5>
            </div>
            <div className="card-body">
              {!result && !error && !loading && (
                <div className="text-center p-5 h-100 d-flex flex-column justify-content-center">
                  <i className="bi bi-arrow-left-circle text-muted mb-3" style={{ fontSize: '3rem' }}></i>
                  <p className="text-muted mb-0">Awaiting input.</p>
                  <small className="text-muted">Paste an artifact and click Verify.</small>
                </div>
              )}
              
              {loading && (
                <div className="text-center p-5 h-100 d-flex flex-column justify-content-center align-items-center">
                  <div className="spinner-border text-primary mb-3" style={{ width: '3rem', height: '3rem' }} role="status">
                    <span className="visually-hidden">Loading...</span>
                  </div>
                  <p className="text-muted">Performing cryptographic verification...</p>
                </div>
              )}

              {error && !loading && (
                <div className="alert alert-dark border-danger text-danger d-flex align-items-center mt-3" role="alert">
                  <i className="bi bi-exclamation-triangle-fill fs-4 me-3"></i>
                  <div>
                    <div className="fw-semibold">{error.message}</div>
                  </div>
                </div>
              )}
              
              {result && !loading && (
                <div className="animation-fade-in">
                  <div className={`alert ${result.valid ? 'alert-success bg-success bg-opacity-10' : 'alert-danger bg-danger bg-opacity-10'} border-0 d-flex align-items-center mb-4`}>
                    <i className={`bi ${result.valid ? 'bi-check-circle-fill text-success' : 'bi-x-circle-fill text-danger'} fs-1 me-3`}></i>
                    <div>
                      <h4 className={`alert-heading mb-1 ${result.valid ? 'text-success' : 'text-danger'} fw-bold`}>
                        {result.valid ? 'Cryptographic Verification: Valid' : 'Cryptographic Verification: Invalid'}
                      </h4>
                      <p className="mb-0 fw-semibold">Reason Code: {result.reason_code}</p>
                    </div>
                  </div>
                  
                  <div className="card bg-black border-secondary mb-4">
                    <div className="card-header border-secondary bg-transparent py-2">
                      <h6 className="text-light mb-0"><i className="bi bi-lock me-2 text-muted"></i>Cryptographic Verification</h6>
                    </div>
                    <div className="card-body py-2">
                      <table className="table table-dark table-borderless table-sm mb-0 align-middle">
                        <tbody>
                          <tr>
                            <td className="text-muted w-25 small">Signature Status</td>
                            <td>
                              <span className={`badge ${result.signature_status === 'valid' ? 'bg-success' : 'bg-danger'}`}>
                                {result.signature_status ? result.signature_status.toUpperCase() : 'UNKNOWN'}
                              </span>
                            </td>
                          </tr>
                          <tr>
                            <td className="text-muted small">Issuer DID</td>
                            <td>
                              <div className="d-flex align-items-center">
                                <span className="font-monospace text-light small text-break me-2">{result.issuer_did || 'Unknown'}</span>
                                {result.issuer_did && (
                                  <button className="btn btn-sm btn-link text-info p-0" onClick={() => copyToClipboard(result.issuer_did, 'Issuer DID')} title="Copy Issuer DID">
                                    <i className="bi bi-clipboard"></i>
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                          <tr>
                            <td className="text-muted small">Subject DID</td>
                            <td>
                              <div className="d-flex align-items-center">
                                <span className="font-monospace text-light small text-break me-2">{result.subject_did || 'Unknown'}</span>
                                {result.subject_did && (
                                  <button className="btn btn-sm btn-link text-info p-0" onClick={() => copyToClipboard(result.subject_did, 'Subject DID')} title="Copy Subject DID">
                                    <i className="bi bi-clipboard"></i>
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                  
                  <div className="card bg-black border-secondary">
                    <div className="card-header border-secondary bg-transparent py-2">
                      <h6 className="text-light mb-0"><i className="bi bi-journal-text me-2 text-muted"></i>Local Registry Status</h6>
                    </div>
                    <div className="card-body">
                      <div className="alert alert-secondary bg-dark border-secondary text-muted small py-2 mb-3 d-flex align-items-start">
                        <i className="bi bi-info-circle me-2 text-info mt-1"></i>
                        <div>Local registry status is specific to the verifying node and should not be interpreted as universal global status.</div>
                      </div>
                      
                      <div className="d-flex align-items-center">
                        <span className="text-muted small me-3">Status:</span>
                        {result.local_status ? (
                          <span className={`badge fs-6 ${result.local_status.toLowerCase() === 'active' ? 'bg-success' : result.local_status.toLowerCase() === 'revoked' ? 'bg-danger' : 'bg-warning'}`}>
                            {result.local_status.toUpperCase()}
                          </span>
                        ) : (
                          <span className="text-muted small">NOT FOUND</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
