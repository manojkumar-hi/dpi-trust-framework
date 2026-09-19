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

  useEffect(() => {
    if (!selectedAgent) {
      setTrustData(null);
      return;
    }
    
    let isMounted = true;
    const fetchTrust = async () => {
      try {
        setLoadingTrust(true);
        setError(null); // Clear previous errors when a new agent is selected
        const data = await trustApi.getTrustScore(selectedAgent);
        if (isMounted) setTrustData(data);
      } catch (err) {
        if (isMounted) {
          setTrustData(null); // Clear old data on error
          if (!err.response) {
            setError({ type: 'network', message: 'Backend Offline: Cannot retrieve trust evaluation' });
          } else if (err.response.status === 401 || err.response.status === 403) {
            setError({ type: 'auth', message: 'Authentication required to view trust evaluations' });
          } else if (err.response.status === 404) {
            setError({ type: 'notfound', message: 'No trust evaluation found for this agent.' });
          } else {
            setError({ type: 'api', message: `Error ${err.response.status}: Failed to load trust evaluation` });
          }
        }
      } finally {
        if (isMounted) setLoadingTrust(false);
      }
    };

    fetchTrust();
    return () => { isMounted = false; };
  }, [selectedAgent]);

  const renderTrustCard = () => {
    if (!trustData) return null;
    
    const trustPercent = (trustData.trust * 100).toFixed(1);
    const beliefPercent = (trustData.belief * 100).toFixed(1);
    const disbeliefPercent = (trustData.disbelief * 100).toFixed(1);
    const uncertaintyPercent = (trustData.uncertainty * 100).toFixed(1);

    return (
      <div className="card bg-dark border-secondary shadow mt-4">
        <div className="card-header border-secondary d-flex justify-content-between align-items-center">
          <h5 className="mb-0 text-light"><i className="bi bi-shield-check text-primary me-2"></i>Subjective Logic Trust Model</h5>
          <span className="badge bg-secondary font-monospace">Agent: {trustData.agent_id}</span>
        </div>
        <div className="card-body">
          <div className="row mb-4">
            <div className="col-12 text-center mb-3">
              <h1 className="display-4 fw-bold text-info">
                {trustPercent}%
              </h1>
              <p className="text-muted text-uppercase small fw-bold tracking-wide">Overall Trust Score</p>
            </div>
            
            <div className="col-12">
              <div className="progress bg-black border border-secondary" style={{ height: '2rem' }}>
                <div className="progress-bar bg-success" style={{ width: `${beliefPercent}%` }} title={`Belief: ${beliefPercent}%`}>
                  {beliefPercent > 10 ? 'Belief' : ''}
                </div>
                <div className="progress-bar bg-danger" style={{ width: `${disbeliefPercent}%` }} title={`Disbelief: ${disbeliefPercent}%`}>
                  {disbeliefPercent > 10 ? 'Disbelief' : ''}
                </div>
                <div className="progress-bar bg-secondary text-dark" style={{ width: `${uncertaintyPercent}%` }} title={`Uncertainty: ${uncertaintyPercent}%`}>
                  {uncertaintyPercent > 10 ? 'Uncertainty' : ''}
                </div>
              </div>
            </div>
          </div>
          
          <div className="row g-4 mt-2">
            <div className="col-md-3 col-6">
              <div className="p-3 bg-black border border-secondary rounded text-center h-100">
                <i className="bi bi-check-circle text-success fs-3 mb-2 d-block"></i>
                <h4 className="text-light mb-1">{beliefPercent}%</h4>
                <small className="text-muted">Belief</small>
              </div>
            </div>
            <div className="col-md-3 col-6">
              <div className="p-3 bg-black border border-secondary rounded text-center h-100">
                <i className="bi bi-x-circle text-danger fs-3 mb-2 d-block"></i>
                <h4 className="text-light mb-1">{disbeliefPercent}%</h4>
                <small className="text-muted">Disbelief</small>
              </div>
            </div>
            <div className="col-md-3 col-6">
              <div className="p-3 bg-black border border-secondary rounded text-center h-100">
                <i className="bi bi-question-circle text-secondary fs-3 mb-2 d-block"></i>
                <h4 className="text-light mb-1">{uncertaintyPercent}%</h4>
                <small className="text-muted">Uncertainty</small>
              </div>
            </div>
            <div className="col-md-3 col-6">
              <div className="p-3 bg-black border border-secondary rounded text-center h-100">
                <i className="bi bi-exclamation-triangle text-warning fs-3 mb-2 d-block"></i>
                <h4 className="text-light mb-1">{trustData.recent_risk.toFixed(2)}</h4>
                <small className="text-muted">Recent Risk</small>
              </div>
            </div>
          </div>
          
          <div className="row mt-4">
            <div className="col-12">
              <h6 className="text-muted mb-3 border-bottom border-secondary pb-2">Evidence Summary</h6>
              <div className="d-flex justify-content-between text-light">
                <span>Positive Evidence Extracted:</span>
                <span className="font-monospace text-success">{trustData.positive_evidence.toFixed(2)} units</span>
              </div>
              <div className="d-flex justify-content-between text-light mt-2">
                <span>Negative Evidence Extracted:</span>
                <span className="font-monospace text-danger">{trustData.negative_evidence.toFixed(2)} units</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="container-fluid relative">
      <div className="row mb-4">
        <div className="col-12">
          <h2>Trust Evaluation</h2>
          <p className="text-muted">Dynamic trust scoring and authorization policies based on verifiable data.</p>
        </div>
      </div>
      
      <div className="row mb-4">
        <div className="col-md-6 col-12">
          <div className="card bg-dark border-secondary">
            <div className="card-body p-3">
              <label htmlFor="agentSelect" className="form-label text-light">Select Agent Identity</label>
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
            </div>
          </div>
        </div>
      </div>

      {loadingTrust && (
        <LoadingState message="Calculating trust evaluation..." />
      )}
      
      {!loadingTrust && error && (
        <div className="card bg-dark border-secondary text-center p-5 mt-4">
          <i className={`bi fs-1 mb-3 ${error.type === 'notfound' ? 'bi-search text-muted' : 'bi-exclamation-triangle text-warning'}`}></i>
          <p className={`mb-0 ${error.type === 'network' ? 'text-danger' : error.type === 'notfound' ? 'text-muted' : 'text-warning'}`}>
            {error.message}
          </p>
        </div>
      )}

      {!loadingTrust && !error && trustData && renderTrustCard()}
      
      {!loadingTrust && !error && !trustData && !selectedAgent && !loadingAgents && (
        <div className="card bg-dark border-secondary text-center p-5 mt-4">
          <i className="bi bi-shield-lock text-muted fs-1 mb-3"></i>
          <p className="text-muted mb-0">No trust evaluations available.</p>
          <small className="text-muted">Select an agent above to view its trust score.</small>
        </div>
      )}
    </div>
  );
};
