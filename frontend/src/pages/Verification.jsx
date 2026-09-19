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
      setError({ type: 'validation', message: 'Please paste a VC JWT artifact to verify.' });
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
        setError({ type: 'network', message: 'Backend Offline: Cannot connect to verification service.' });
      } else if (err.response.status === 401 || err.response.status === 403) {
        setError({ type: 'auth', message: 'Authentication required for verification service.' });
      } else {
        const msg = err.response.data?.detail || `Error ${err.response.status}: Verification request failed`;
        setError({ type: 'api', message: typeof msg === 'string' ? msg : JSON.stringify(msg) });
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

  return (
    <div className="container-fluid relative">
      <div className="row mb-4">
        <div className="col-12">
          <h2>VC Artifact Verifier</h2>
          <p className="text-muted">Stateless, cryptographic verification of Verifiable Credential JWT artifacts.</p>
        </div>
      </div>
      
      <div className="row">
        <div className="col-lg-6 mb-4">
          <div className="card bg-dark border-secondary h-100">
            <div className="card-header border-secondary d-flex justify-content-between align-items-center">
              <h5 className="mb-0 text-light"><i className="bi bi-file-earmark-lock text-primary me-2"></i>Input VC Artifact</h5>
            </div>
            <div className="card-body d-flex flex-column">
              <p className="text-muted small mb-3">
                Paste a raw W3C vc+jwt string below. The backend will parse the token, resolve the embedded Issuer DID to fetch their public key, and mathematically verify the EdDSA signature.
              </p>
              
              <textarea 
                className="form-control bg-black text-light border-secondary font-monospace flex-grow-1 mb-3" 
                rows="10" 
                placeholder="eyJhbGciOiJFZERTQSIsInR5cCI6InZjK2p3dCJ9..."
                value={jwt}
                onChange={(e) => setJwt(e.target.value)}
                style={{ fontSize: '0.85rem' }}
                disabled={loading}
              ></textarea>
              
              <div className="d-flex justify-content-between mt-auto">
                <button 
                  className="btn btn-outline-secondary" 
                  onClick={handleClear}
                  disabled={loading || (!jwt && !result && !error)}
                >
                  <i className="bi bi-trash"></i> Clear
                </button>
                <button 
                  className="btn btn-primary" 
                  onClick={handleVerify}
                  disabled={loading || !jwt.trim()}
                >
                  {loading ? (
                    <><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Verifying...</>
                  ) : (
                    <><i className="bi bi-shield-check"></i> Verify Credential</>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
        
        <div className="col-lg-6 mb-4">
          <div className="card bg-dark border-secondary h-100">
            <div className="card-header border-secondary">
              <h5 className="mb-0 text-light"><i className="bi bi-shield-shaded text-info me-2"></i>Verification Result</h5>
            </div>
            <div className="card-body">
              {!result && !error && !loading && (
                <div className="text-center p-5">
                  <i className="bi bi-arrow-left-circle text-muted fs-1 mb-3"></i>
                  <p className="text-muted mb-0">Awaiting input.</p>
                  <small className="text-muted">Paste an artifact and click Verify.</small>
                </div>
              )}
              
              {loading && (
                <div className="text-center p-5">
                  <div className="spinner-border text-primary mb-3" role="status">
                    <span className="visually-hidden">Loading...</span>
                  </div>
                  <p className="text-muted">Performing cryptographic verification...</p>
                </div>
              )}

              {error && !loading && (
                <div className="alert alert-dark border-danger text-danger d-flex align-items-center" role="alert">
                  <i className="bi bi-exclamation-triangle-fill fs-4 me-3"></i>
                  <div>
                    <strong>Verification Request Failed</strong>
                    <div className="small mt-1">{error.message}</div>
                  </div>
                </div>
              )}
              
              {result && !loading && (
                <div>
                  <div className={`alert ${result.valid ? 'alert-success bg-success bg-opacity-10' : 'alert-danger bg-danger bg-opacity-10'} border-0 d-flex align-items-center mb-4`}>
                    <i className={`bi ${result.valid ? 'bi-check-circle-fill text-success' : 'bi-x-circle-fill text-danger'} fs-1 me-3`}></i>
                    <div>
                      <h4 className={`alert-heading mb-1 ${result.valid ? 'text-success' : 'text-danger'}`}>
                        {result.valid ? 'Cryptographically Valid' : 'Invalid Verification'}
                      </h4>
                      <p className="mb-0">{result.reason_code}</p>
                    </div>
                  </div>
                  
                  <h6 className="text-muted mb-3 border-bottom border-secondary pb-2">Cryptographic Validation</h6>
                  <div className="row mb-4">
                    <div className="col-12 mb-2">
                      <span className="text-muted d-block small">Signature Status</span>
                      <span className={`badge ${result.signature_status === 'valid' ? 'bg-success' : 'bg-danger'}`}>
                        {result.signature_status}
                      </span>
                    </div>
                    <div className="col-12 mb-2">
                      <span className="text-muted d-block small">Issuer DID</span>
                      <span className="font-monospace text-light small text-break">{result.issuer_did || 'Unknown'}</span>
                    </div>
                    <div className="col-12 mb-2">
                      <span className="text-muted d-block small">Subject DID</span>
                      <span className="font-monospace text-light small text-break">{result.subject_did || 'Unknown'}</span>
                    </div>
                  </div>
                  
                  <h6 className="text-muted mb-3 border-bottom border-secondary pb-2">Local Registry Status (Optional)</h6>
                  <div className="row">
                    <div className="col-12">
                      <p className="text-muted small mb-2">
                        <i className="bi bi-info-circle me-1"></i>
                        The local status indicates the state of this credential within this node's database. It does NOT guarantee universal revocation state across the entire trust framework.
                      </p>
                      <span className="text-muted d-block small mb-1">Local Ledger Status</span>
                      {result.local_status ? (
                        <span className={`badge ${result.local_status === 'active' ? 'bg-success' : 'bg-warning'}`}>
                          {result.local_status}
                        </span>
                      ) : (
                        <span className="text-muted small">Not found in local ledger</span>
                      )}
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
