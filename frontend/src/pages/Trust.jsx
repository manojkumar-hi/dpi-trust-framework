import React, { useState, useEffect } from 'react';
import { trustApi } from '../api/trust';
import { agentsApi } from '../api/agents';
import { LoadingState } from '../components/common/LoadingState';

export const Trust = () => {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState('');
  const [trustData, setTrustData] = useState(null);
  
  const [loadingAgents, setLoadingAgents] = useState(true);
  const [loadingTrust, setLoadingTrust] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    const fetchAgents = async () => {
      try {
        setLoadingAgents(true);
        const data = await agentsApi.getAgents();
        if (isMounted) setAgents(data);
      } catch (err) {
        if (isMounted) {
          if (!err.response) {
            setError({ type: 'network', message: 'Backend Offline: Cannot retrieve agent registry' });
          } else {
            setError({ type: 'api', message: 'Failed to load agent registry for selection' });
          }
        }
      } finally {
        if (isMounted) setLoadingAgents(false);
      }
    };
    fetchAgents();
    return () => { isMounted = false; };
  }, []);

  const fetchTrust = async (agentId) => {
    if (!agentId) return;
    try {
      setLoadingTrust(true);
      setError(null);
      setTrustData(null);
      const data = await trustApi.getTrustScore(agentId);
      
      // Validate expected structure to prevent malformed data rendering
      if (
        typeof data.belief !== 'number' ||
        typeof data.disbelief !== 'number' ||
        typeof data.uncertainty !== 'number' ||
        typeof data.trust !== 'number' ||
        typeof data.recent_risk !== 'number' ||
        typeof data.positive_evidence !== 'number' ||
        typeof data.negative_evidence !== 'number'
      ) {
        throw new Error('Malformed trust evaluation payload returned from backend.');
      }
      
      setTrustData(data);
    } catch (err) {
      setTrustData(null);
      if (err.message === 'Malformed trust evaluation payload returned from backend.') {
        setError({ type: 'data', message: err.message });
      } else if (!err.response) {
        setError({ type: 'network', message: 'Backend Offline: Cannot retrieve trust evaluation' });
      } else if (err.response.status === 401 || err.response.status === 403) {
        setError({ type: 'auth', message: 'Authentication required to view trust evaluations' });
      } else if (err.response.status === 404) {
        setError({ type: 'notfound', message: 'No trust evaluation found for this agent.' });
      } else {
        setError({ type: 'api', message: `Error ${err.response.status}: Failed to load trust evaluation` });
      }
    } finally {
      setLoadingTrust(false);
    }
  };

  useEffect(() => {
    if (selectedAgent) {
      fetchTrust(selectedAgent);
    } else {
      setTrustData(null);
      setError(null);
    }
    // We intentionally don't want this to run again unless selectedAgent changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAgent]);

  const handleRefresh = () => {
    if (selectedAgent) {
      fetchTrust(selectedAgent);
    }
  };

  const renderTrustCard = () => {
    if (!trustData) return null;
    
    // Per instructions: use returned values directly, no clamping/normalizing.
    const tVal = trustData.trust;
    const bVal = trustData.belief;
    const dVal = trustData.disbelief;
    const uVal = trustData.uncertainty;
    const rRisk = trustData.recent_risk;

    // Direct percentage strings for visual widths and text display
    const bPct = (bVal * 100).toFixed(1) + '%';
    const dPct = (dVal * 100).toFixed(1) + '%';
    const uPct = (uVal * 100).toFixed(1) + '%';
    const tPct = (tVal * 100).toFixed(1) + '%';

    return (
      <div className="card bg-dark border-secondary shadow mt-4">
        <div className="card-header border-secondary d-flex justify-content-between align-items-center flex-wrap gap-2 py-3 bg-transparent">
          <h5 className="mb-0 text-light"><i className="bi bi-shield-check text-primary me-2"></i>Subjective Logic Model</h5>
          {trustData.timestamp && (
            <span className="text-muted small">Evaluated: {new Date(trustData.timestamp).toLocaleString()}</span>
          )}
        </div>
        <div className="card-body">
          <div className="row mb-5">
            <div className="col-md-3 text-center border-end border-secondary mb-4 mb-md-0 d-flex flex-column justify-content-center">
              <h1 className="display-4 fw-bold text-light mb-0">
                {tVal.toFixed(2)}
              </h1>
              <div className="text-info fs-4 mb-2">{tPct}</div>
              <p className="text-muted text-uppercase small fw-bold tracking-wide mb-0">Trust Score</p>
            </div>
            
            <div className="col-md-9 d-flex flex-column justify-content-center ps-md-4">
              <h6 className="text-muted mb-3">Trust Composition (Raw Values)</h6>
              <div className="progress bg-black border border-secondary mb-3 rounded-0" style={{ height: '2.5rem' }}>
                <div className="progress-bar bg-primary" style={{ width: bPct }} title={`Belief: ${bPct}`}>
                  {bVal > 0.05 ? bPct : ''}
                </div>
                <div className="progress-bar bg-warning text-dark" style={{ width: dPct }} title={`Disbelief: ${dPct}`}>
                  {dVal > 0.05 ? dPct : ''}
                </div>
                <div className="progress-bar bg-secondary text-dark" style={{ width: uPct }} title={`Uncertainty: ${uPct}`}>
                  {uVal > 0.05 ? uPct : ''}
                </div>
              </div>
              <div className="d-flex justify-content-between text-muted small px-1">
                <span><i className="bi bi-circle-fill text-primary me-1"></i>Belief: {bVal.toFixed(2)}</span>
                <span><i className="bi bi-circle-fill text-warning me-1"></i>Disbelief: {dVal.toFixed(2)}</span>
                <span><i className="bi bi-circle-fill text-secondary me-1"></i>Uncertainty: {uVal.toFixed(2)}</span>
              </div>
            </div>
          </div>
          
          <div className="row g-4 mb-4">
            <div className="col-md-6">
              <div className="card bg-black border-secondary h-100">
                <div className="card-body">
                  <h6 className="text-light border-bottom border-secondary pb-2 mb-3"><i className="bi bi-file-earmark-bar-graph me-2"></i>Evidence Accumulation</h6>
                  <div className="d-flex justify-content-between align-items-center mb-2">
                    <span className="text-muted">Positive Evidence:</span>
                    <span className="badge bg-dark border border-secondary fs-6 text-light">{trustData.positive_evidence}</span>
                  </div>
                  <div className="d-flex justify-content-between align-items-center">
                    <span className="text-muted">Negative Evidence:</span>
                    <span className="badge bg-dark border border-secondary fs-6 text-light">{trustData.negative_evidence}</span>
                  </div>
                </div>
              </div>
            </div>
            <div className="col-md-6">
              <div className="card bg-black border-secondary h-100">
                <div className="card-body">
                  <h6 className="text-light border-bottom border-secondary pb-2 mb-3"><i className="bi bi-shield-exclamation me-2"></i>Recent Risk Assessment</h6>
                  <div className="d-flex align-items-center">
                    <h2 className="text-light fw-bold mb-0 me-3">{rRisk.toFixed(2)}</h2>
                    <span className="text-muted small">Current risk indicator.</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <div className="alert alert-secondary bg-dark border-secondary text-muted small py-3 mb-0 shadow-sm d-flex align-items-start">
            <i className="bi bi-info-circle me-3 fs-5 text-info mt-1"></i>
            <div>
              <strong className="d-block mb-2 text-light">Trust State Explanation</strong>
              <ul className="mb-0 ps-3">
                <li className="mb-1"><strong>Belief</strong> represents positive evidence support.</li>
                <li className="mb-1"><strong>Disbelief</strong> represents negative evidence support.</li>
                <li className="mb-1"><strong>Uncertainty</strong> represents remaining uncertainty.</li>
                <li className="mb-1"><strong>Trust</strong> is the backend-computed trust value.</li>
                <li><strong>Recent Risk</strong> represents the backend recent-risk indicator.</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="container-fluid position-relative">
      <div className="row mb-4">
        <div className="col-12">
          <h2 className="mb-1 fw-bold">Trust Evaluation</h2>
          <p className="text-muted fs-6 mb-0">Dynamic trust state derived from behavioral evidence and security signals.</p>
        </div>
      </div>
      
      <div className="row mb-4">
        <div className="col-md-8 col-lg-6 col-12">
          <div className="card bg-dark border-secondary shadow-sm">
            <div className="card-body p-3">
              <label htmlFor="agentSelect" className="form-label text-light fw-semibold">Select Agent</label>
              <div className="d-flex gap-2">
                <select 
                  id="agentSelect"
                  className="form-select bg-black text-light border-secondary"
                  value={selectedAgent}
                  onChange={(e) => setSelectedAgent(e.target.value)}
                  disabled={loadingAgents || agents.length === 0}
                >
                  <option value="">{loadingAgents ? 'Loading agents...' : agents.length === 0 ? 'No agents found' : '-- Select an Agent --'}</option>
                  {agents.map(agent => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name} ({agent.did || agent.id.substring(0,8) + '...'})
                    </option>
                  ))}
                </select>
                <button 
                  className="btn btn-outline-info text-nowrap"
                  onClick={handleRefresh}
                  disabled={!selectedAgent || loadingTrust}
                >
                  {loadingTrust ? <span className="spinner-border spinner-border-sm me-2" role="status"></span> : <i className="bi bi-arrow-clockwise me-2"></i>}
                  Refresh Evaluation
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {loadingTrust && (
        <LoadingState message="Fetching current trust state..." />
      )}
      
      {!loadingTrust && error && (
        <div className="card bg-dark border-secondary text-center p-5 mt-4 shadow-sm">
          <i className={`bi fs-1 mb-3 ${error.type === 'notfound' ? 'bi-search text-muted' : 'bi-exclamation-triangle text-warning'}`}></i>
          <p className={`mb-0 ${error.type === 'network' ? 'text-danger' : error.type === 'notfound' ? 'text-muted' : 'text-warning'}`}>
            {error.message}
          </p>
        </div>
      )}

      {!loadingTrust && !error && trustData && renderTrustCard()}
      
      {!loadingTrust && !error && !trustData && !selectedAgent && !loadingAgents && (
        <div className="card bg-dark border-secondary text-center p-5 mt-4 shadow-sm">
          <i className="bi bi-shield-lock text-muted fs-1 mb-3"></i>
          <p className="text-muted mb-0">No agent selected.</p>
          <small className="text-muted">Select an agent above to view its trust state.</small>
        </div>
      )}
    </div>
  );
};
