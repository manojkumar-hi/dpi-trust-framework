import React, { useState, useEffect } from 'react';
import { agentsApi } from '../api/agents';
import { LoadingState } from '../components/common/LoadingState';
import { StatusBadge } from '../components/common/StatusBadge';

export const Agents = () => {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    
    const fetchAgents = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await agentsApi.getAgents();
        if (isMounted) {
          setAgents(data);
        }
      } catch (err) {
        if (isMounted) {
          if (!err.response) {
            setError({ type: 'network', message: 'Backend Offline: Cannot retrieve agents' });
          } else if (err.response.status === 401 || err.response.status === 403) {
            setError({ type: 'auth', message: 'Authentication required to view agents' });
          } else {
            setError({ type: 'api', message: `Error ${err.response.status}: Failed to load agents` });
          }
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchAgents();
    
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="container-fluid">
      <div className="row mb-4">
        <div className="col-12">
          <h2>Agents</h2>
          <p className="text-muted">Agent identities registered with the Trust Framework.</p>
        </div>
      </div>
      
      {loading ? (
        <LoadingState message="Loading agent registry..." />
      ) : error ? (
        <div className="card bg-dark border-secondary text-center p-5">
          <i className="bi bi-exclamation-triangle text-warning fs-1 mb-3"></i>
          <p className={`mb-0 ${error.type === 'network' ? 'text-danger' : 'text-warning'}`}>{error.message}</p>
        </div>
      ) : agents.length === 0 ? (
        <div className="card bg-dark border-secondary text-center p-5">
          <i className="bi bi-robot text-muted fs-1 mb-3"></i>
          <p className="text-muted mb-0">No agents found in the registry.</p>
        </div>
      ) : (
        <div className="card bg-dark border-secondary">
          <div className="table-responsive">
            <table className="table table-dark table-hover mb-0">
              <thead>
                <tr>
                  <th className="border-secondary">Agent Name</th>
                  <th className="border-secondary">Agent ID</th>
                  <th className="border-secondary">Type</th>
                  <th className="border-secondary">Organization ID</th>
                  <th className="border-secondary">Status</th>
                  <th className="border-secondary">Registered Date</th>
                </tr>
              </thead>
              <tbody>
                {agents.map(agent => (
                  <tr key={agent.id}>
                    <td className="border-secondary align-middle">
                      <div className="d-flex align-items-center">
                        <i className="bi bi-robot me-2 text-primary"></i>
                        <strong>{agent.name}</strong>
                      </div>
                      {agent.description && <div className="small text-muted">{agent.description}</div>}
                    </td>
                    <td className="border-secondary align-middle text-muted font-monospace small">{agent.id}</td>
                    <td className="border-secondary align-middle">{agent.agent_type}</td>
                    <td className="border-secondary align-middle text-muted font-monospace small">{agent.organization_id}</td>
                    <td className="border-secondary align-middle"><StatusBadge status={agent.status} /></td>
                    <td className="border-secondary align-middle text-muted small">{new Date(agent.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
