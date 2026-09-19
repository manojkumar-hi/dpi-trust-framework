import React, { useState, useEffect } from 'react';
import { StatCard } from '../components/common/StatCard';
import { dashboardApi } from '../api/dashboard';
import { LoadingState } from '../components/common/LoadingState';
import { useAuth } from '../context/AuthContext';

export const Dashboard = () => {
  const { isAuthenticated } = useAuth();
  const [data, setData] = useState({
    organizations: null,
    agents: null,
    credentials: null,
    delegations: null,
    auditLogs: null
  });
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState({});
  const [networkError, setNetworkError] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const fetchData = async () => {
      setLoading(true);
      setNetworkError(false);
      const newData = { organizations: '—', agents: '—', credentials: '—', delegations: '—', auditLogs: '—' };
      const newErrors = {};
      let isOffline = false;

      const fetchMetric = async (key, apiCall) => {
        try {
          const result = await apiCall();
          if (isMounted) {
            newData[key] = Array.isArray(result) ? result.length : (result?.count ?? result?.length ?? '—');
          }
        } catch (err) {
          if (isMounted) {
            if (!err.response) {
              isOffline = true;
            } else {
              newErrors[key] = err.response.status;
            }
            newData[key] = '—';
          }
        }
      };

      await Promise.allSettled([
        fetchMetric('organizations', dashboardApi.getOrganizations),
        fetchMetric('agents', dashboardApi.getAgents),
        fetchMetric('credentials', dashboardApi.getCredentials),
        fetchMetric('delegations', dashboardApi.getDelegations),
        fetchMetric('auditLogs', dashboardApi.getAuditLogs)
      ]);

      if (isMounted) {
        setNetworkError(isOffline);
        setData(newData);
        setErrors(newErrors);
        setLoading(false);
      }
    };

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [isAuthenticated]);

  const getMetricDescription = (key) => {
    if (networkError) return <span className="text-danger">Backend Offline</span>;
    if (errors[key] === 401 || errors[key] === 403) return <span className="text-warning">Authentication required</span>;
    if (errors[key] === 404) return <span className="text-warning">Not found</span>;
    if (errors[key]) return <span className="text-danger">Error {errors[key]}</span>;
    if (data[key] === 0) return 'No records found';
    if (data[key] !== null && data[key] !== '—') return 'Active records';
    return 'Not available';
  };

  return (
    <div className="container-fluid">
      <div className="row mb-4">
        <div className="col-12">
          <h2 className="mb-1">DPI Trust Framework</h2>
          <p className="text-muted fs-5">Identity, Credentials & Trust for Agentic AI</p>
        </div>
      </div>

      {loading ? (
        <LoadingState message="Loading dashboard metrics..." />
      ) : (
        <div className="row mb-4">
          <div className="col-md-3">
            <StatCard title="Organizations" value={data.organizations} icon="building" description={getMetricDescription('organizations')} />
          </div>
          <div className="col-md-3">
            <StatCard title="Agents" value={data.agents} icon="robot" description={getMetricDescription('agents')} />
          </div>
          <div className="col-md-3">
            <StatCard title="Credentials" value={data.credentials} icon="card-heading" description={getMetricDescription('credentials')} />
          </div>
          <div className="col-md-3">
            <StatCard title="Delegations" value={data.delegations} icon="diagram-3" description={getMetricDescription('delegations')} />
          </div>
        </div>
      )}

      <div className="row mb-4">
        <div className="col-12">
          <div className="card bg-dark border-secondary">
            <div className="card-header border-secondary bg-transparent">
              <h5 className="mb-0">Trust Decision Pipeline</h5>
            </div>
            <div className="card-body">
              <div className="d-flex flex-column align-items-center text-center">
                <div className="p-3 bg-secondary rounded bg-opacity-25 border border-secondary mb-2 w-50">Agent Identity</div>
                <i className="bi bi-arrow-down fs-4 text-muted mb-2"></i>
                <div className="p-3 bg-secondary rounded bg-opacity-25 border border-secondary mb-2 w-50">Verifiable Credential</div>
                <i className="bi bi-arrow-down fs-4 text-muted mb-2"></i>
                <div className="p-3 bg-secondary rounded bg-opacity-25 border border-secondary mb-2 w-50">Delegation</div>
                <i className="bi bi-arrow-down fs-4 text-muted mb-2"></i>
                <div className="p-3 bg-secondary rounded bg-opacity-25 border border-secondary mb-2 w-50">Credential Status</div>
                <i className="bi bi-arrow-down fs-4 text-muted mb-2"></i>
                <div className="p-3 bg-secondary rounded bg-opacity-25 border border-secondary mb-2 w-50">Trust Evaluation</div>
                <i className="bi bi-arrow-down fs-4 text-muted mb-2"></i>
                <div className="p-3 bg-secondary rounded bg-opacity-25 border border-primary mb-2 w-50 text-primary fw-bold">Policy Authorization</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="row">
        <div className="col-12">
          <div className="card bg-dark border-secondary">
            <div className="card-header border-secondary bg-transparent d-flex justify-content-between align-items-center">
              <h5 className="mb-0">System Capabilities</h5>
              {!loading && (
                <span className="text-muted small">
                  Audit Logs: {getMetricDescription('auditLogs')} {data.auditLogs !== '—' ? `(${data.auditLogs})` : ''}
                </span>
              )}
            </div>
            <div className="card-body">
              <ul className="list-group list-group-flush bg-transparent">
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Decentralized Agent Identity</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Verifiable Credentials</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Cryptographic Delegation</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Dynamic Trust Evaluation</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Policy-Based Authorization</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Cryptographic Revocation</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Cross-Organization Verification</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Audit & Traceability</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Hyperledger Fabric Anchoring</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
