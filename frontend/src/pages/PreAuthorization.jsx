import React, { useEffect, useMemo, useState } from 'react';
import { agentsApi } from '../api/agents';
import { authorizationApi } from '../api/authorization';
import { delegationsApi } from '../api/delegations';
import { useAuth } from '../context/AuthContext';

export const PreAuthorization = () => {
  const { orgId } = useAuth();
  const [agents, setAgents] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [delegations, setDelegations] = useState([]);
  const [agentId, setAgentId] = useState('');
  const [actionType, setActionType] = useState('');
  const [delegationId, setDelegationId] = useState('');
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [agentRecords, templateRecords, delegationRecords] = await Promise.all([
          agentsApi.getAgents(orgId),
          agentsApi.getTemplates(),
          delegationsApi.getDelegations(),
        ]);
        setAgents(agentRecords.filter((agent) => agent.status === 'active'));
        setTemplates(templateRecords);
        setDelegations(delegationRecords);
      } catch {
        setError('Unable to load agents, actions, or delegations.');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [orgId]);

  const selectedAgent = agents.find((agent) => agent.id === agentId);
  const selectedTemplate = templates.find((template) => (
    template.template_id === selectedAgent?.template_id
      && template.template_version === selectedAgent?.template_version
  ));
  const actions = selectedTemplate?.tools || [];
  const applicableDelegations = useMemo(() => delegations.filter((delegation) => (
    delegation.delegatee_agent_id === agentId && delegation.status === 'active'
  )), [agentId, delegations]);

  const selectAgent = (nextAgentId) => {
    setAgentId(nextAgentId);
    setActionType('');
    setDelegationId('');
    setResult(null);
    setError('');
  };

  const checkAuthorization = async (event) => {
    event.preventDefault();
    setChecking(true);
    setError('');
    setResult(null);
    try {
      setResult(await authorizationApi.preCheck({ agentId, actionType, delegationId }));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'The pre-authorization check could not be completed.');
    } finally {
      setChecking(false);
    }
  };

  if (loading) return <div className="container-fluid py-4 text-muted">Loading pre-authorization workspace…</div>;

  return (
    <div className="container-fluid py-4">
      <div className="mb-4">
        <h2 className="text-light mb-1"><i className="bi bi-shield-lock me-2 text-primary"></i>Pre-Authorization Check</h2>
        <p className="text-muted mb-0">Test whether an agent can perform a proposed action. This does not execute the action.</p>
      </div>

      <div className="row g-4">
        <div className="col-lg-6">
          <div className="card bg-dark border-secondary h-100">
            <div className="card-body">
              {error && <div className="alert alert-danger">{typeof error === 'string' ? error : JSON.stringify(error)}</div>}
              <form onSubmit={checkAuthorization}>
                <div className="mb-3">
                  <label className="form-label text-light">Agent</label>
                  <select className="form-select bg-dark border-secondary text-light" value={agentId} onChange={(event) => selectAgent(event.target.value)} required>
                    <option value="">Select an agent…</option>
                    {agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name} ({agent.agent_type})</option>)}
                  </select>
                </div>
                <div className="mb-3">
                  <label className="form-label text-light">Proposed action</label>
                  <select className="form-select bg-dark border-secondary text-light" value={actionType} onChange={(event) => { setActionType(event.target.value); setResult(null); }} disabled={!selectedTemplate} required>
                    <option value="">{selectedTemplate ? 'Select an action…' : 'Select an agent role first'}</option>
                    {actions.map((tool) => <option key={tool.capability_code} value={tool.capability_code}>{tool.name} — {tool.capability_code}</option>)}
                  </select>
                  {selectedAgent && !selectedTemplate && <div className="form-text text-warning">This agent has no registered actions.</div>}
                </div>
                <div className="mb-4">
                  <label className="form-label text-light">Delegation</label>
                  <select className="form-select bg-dark border-secondary text-light" value={delegationId} onChange={(event) => { setDelegationId(event.target.value); setResult(null); }} disabled={!agentId}>
                    <option value="">No delegation selected</option>
                    {applicableDelegations.map((delegation) => <option key={delegation.id} value={delegation.id}>{delegation.purpose} — expires {new Date(delegation.expires_at).toLocaleDateString()}</option>)}
                  </select>
                  <div className="form-text text-muted">The check verifies the selected delegation against live lifecycle and ledger evidence.</div>
                </div>
                <button className="btn btn-primary" type="submit" disabled={checking || !agentId || !actionType}>
                  {checking ? <span className="spinner-border spinner-border-sm me-2"></span> : <i className="bi bi-search me-2"></i>}
                  Run pre-check
                </button>
              </form>
            </div>
          </div>
        </div>

        <div className="col-lg-6">
          <div className="card bg-dark border-secondary h-100">
            <div className="card-header border-secondary bg-transparent"><h5 className="mb-0 text-light">Decision</h5></div>
            <div className="card-body">
              {!result && <p className="text-muted mb-0">Select an agent, proposed action, and delegation to see an explainable authorization decision.</p>}
              {result && <>
                <div className={`alert ${result.is_allowed ? 'alert-success' : 'alert-danger'}`}>
                  <div className="fw-bold fs-5">{result.is_allowed ? 'Allowed' : 'Denied'}</div>
                  <div>{result.explanation}</div>
                </div>
                <dl className="row mb-0">
                  <dt className="col-sm-5 text-muted">Reason</dt><dd className="col-sm-7 text-light font-monospace">{result.reason_code}</dd>
                  <dt className="col-sm-5 text-muted">Policy target</dt><dd className="col-sm-7 text-light">{result.resource_type} / {result.action_type}</dd>
                  <dt className="col-sm-5 text-muted">Required capability</dt><dd className="col-sm-7 text-light">{result.evidence.required_capability || 'None'}</dd>
                  <dt className="col-sm-5 text-muted">Delegation valid</dt><dd className="col-sm-7 text-light">{String(result.evidence.delegation_validity)}</dd>
                  <dt className="col-sm-5 text-muted">Trust score</dt><dd className="col-sm-7 text-light">{result.evidence.actual_trust}</dd>
                </dl>
              </>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
