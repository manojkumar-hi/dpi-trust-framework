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
    auditLogs: null,
    auditLogsRaw: []
  });
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState({});
  const [networkError, setNetworkError] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const fetchData = async () => {
      setLoading(true);
      setNetworkError(false);
      const newData = { organizations: '—', agents: '—', credentials: '—', delegations: '—', auditLogs: '—', auditLogsRaw: [] };
      const newErrors = {};
      let isOffline = false;

      const fetchMetric = async (key, apiCall, storeRaw = false) => {
        try {
          const result = await apiCall();
          if (isMounted) {
            newData[key] = Array.isArray(result) ? result.length : (result?.count ?? result?.length ?? '—');
            if (storeRaw) {
              newData[`${key}Raw`] = Array.isArray(result) ? result : (result?.items ?? []);
            }
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
        fetchMetric('auditLogs', dashboardApi.getAuditLogs, true)
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

  const recentAudits = [...data.auditLogsRaw]
    .sort((a, b) => new Date(b.occurred_at) - new Date(a.occurred_at))
    .slice(0, 5);

  return (
    <div className="container-fluid">
      <div className="row mb-4">
        <div className="col-12">
          <h2 className="mb-1 fw-bold">Dashboard</h2>
          <p className="text-muted fs-6">DPI Trust Framework Overview</p>
        </div>
      </div>

      {loading ? (
        <LoadingState message="Loading dashboard metrics..." />
      ) : (
        <>
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

          <div className="row mb-4">
            <div className="col-lg-6 mb-4 mb-lg-0">
              <div className="card bg-dark border-secondary h-100 shadow-sm">
                <div className="card-header border-secondary bg-transparent py-3">
                  <h6 className="mb-0 fw-semibold text-light"><i className="bi bi-funnel me-2"></i>Trust Decision Pipeline</h6>
                </div>
                <div className="card-body d-flex align-items-center justify-content-center p-4">
                  <div className="d-flex flex-column align-items-center text-center w-100">
                    <div className="p-3 bg-secondary rounded bg-opacity-25 border border-secondary mb-2 w-75 shadow-sm">Agent Identity</div>
                    <i className="bi bi-arrow-down fs-4 text-primary mb-2"></i>
                    <div className="p-3 bg-secondary rounded bg-opacity-25 border border-secondary mb-2 w-75 shadow-sm">Verifiable Credential</div>
                    <i className="bi bi-arrow-down fs-4 text-primary mb-2"></i>
                    <div className="p-3 bg-secondary rounded bg-opacity-25 border border-secondary mb-2 w-75 shadow-sm">Delegation</div>
                    <i className="bi bi-arrow-down fs-4 text-primary mb-2"></i>
                    <div className="p-3 bg-secondary rounded bg-opacity-25 border border-secondary mb-2 w-75 shadow-sm">Trust Evaluation</div>
                    <i className="bi bi-arrow-down fs-4 text-primary mb-2"></i>
                    <div className="p-3 bg-primary rounded bg-opacity-10 border border-primary text-primary fw-bold w-75 shadow-sm">Policy Authorization</div>
                  </div>
                </div>
              </div>
            </div>

            <div className="col-lg-6">
              <div className="card bg-dark border-secondary h-100 shadow-sm">
                <div className="card-header border-secondary bg-transparent py-3 d-flex justify-content-between align-items-center">
                  <h6 className="mb-0 fw-semibold text-light"><i className="bi bi-activity me-2"></i>Recent Activity</h6>
                  <span className="badge bg-primary rounded-pill">{data.auditLogs !== '—' ? data.auditLogs : 0} Total</span>
                </div>
                <div className="card-body p-0">
                  {recentAudits.length > 0 ? (
                    <div className="list-group list-group-flush">
                      {recentAudits.map((audit) => (
                        <div key={audit.id} className="list-group-item bg-transparent text-light border-secondary p-3">
                          <div className="d-flex w-100 justify-content-between align-items-center mb-1">
                            <h6 className="mb-0 text-truncate" style={{ maxWidth: '70%' }}>
                              {audit.event_type}
                            </h6>
                            <small className="text-muted text-nowrap">
                              {new Date(audit.occurred_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </small>
                          </div>
                          <p className="mb-0 text-muted small text-truncate">
                            <span className="badge bg-secondary me-2">{audit.event_category}</span>
                            {audit.actor_did ? `Actor: ${audit.actor_did}` : (audit.actor_organization_id ? `Org: ${audit.actor_organization_id}` : 'System Event')}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-4 text-center text-muted">
                      <i className="bi bi-inbox fs-2 mb-2 d-block"></i>
                      <p className="mb-0">No recent activity found.</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
