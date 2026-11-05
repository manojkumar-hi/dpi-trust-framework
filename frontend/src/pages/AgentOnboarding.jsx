import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { agentsApi } from '../api/agents';
import { useAuth } from '../context/AuthContext';

const makeDraft = () => ({
  id: `${Date.now()}-${Math.random()}`,
  templateId: '',
  name: '',
  description: '',
  status: 'pending',
  error: ''
});

const formatError = (error, fallback) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      const location = Array.isArray(item?.loc) ? item.loc.filter((part) => part !== 'body') : [];
      const field = location.length ? String(location[location.length - 1]).replaceAll('_', ' ') : '';
      const message = typeof item?.msg === 'string' ? item.msg : 'Invalid value';
      return field ? `${field}: ${message}` : message;
    }).join('; ') || fallback;
  }
  return fallback;
};

export const AgentOnboarding = () => {
  const { orgId, currentUser } = useAuth();
  const navigate = useNavigate();
  const [templates, setTemplates] = useState([]);
  const [drafts, setDrafts] = useState([makeDraft()]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [pageError, setPageError] = useState('');

  useEffect(() => {
    let mounted = true;
    agentsApi.getTemplates()
      .then((availableTemplates) => {
        if (!mounted) return;
        setTemplates(availableTemplates);
        setDrafts((current) => current.map((draft) => ({
          ...draft,
          templateId: draft.templateId || availableTemplates[0]?.template_id || '',
        })));
      })
      .catch((error) => {
        if (mounted) setPageError(formatError(error, 'Unable to load agent setup.'));
      })
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, [navigate]);

  const updateDraft = (id, updates) => {
    setDrafts((current) => current.map((draft) => draft.id === id ? { ...draft, ...updates } : draft));
  };

  const chooseTemplate = (draft, templateId) => {
    updateDraft(draft.id, {
      templateId,
    });
  };

  const submit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setPageError('');
    const candidates = drafts.filter((draft) => draft.status !== 'success');
    for (const draft of candidates) {
      const template = templates.find((item) => item.template_id === draft.templateId);
      if (!template || !draft.name.trim()) {
        updateDraft(draft.id, { status: 'failed', error: 'Choose an agent role and provide an agent name.' });
        continue;
      }
      updateDraft(draft.id, { status: 'submitting', error: '' });
      try {
        await agentsApi.registerFromTemplate({
          organization_id: orgId,
          name: draft.name.trim(),
          description: draft.description.trim() || null,
          template_id: template.template_id,
          template_version: template.template_version,
        });
        updateDraft(draft.id, { status: 'success', error: '' });
      } catch (error) {
        updateDraft(draft.id, { status: 'failed', error: formatError(error, 'Agent registration failed.') });
      }
    }
    setSubmitting(false);
  };

  if (loading) return <div className="container py-5 text-light">Loading available agent roles...</div>;

  return (
    <div className="container py-4">
      <div className="mb-4">
        <h2 className="text-light mb-1">Set up your agents</h2>
        <p className="text-muted mb-0">Register agents for {currentUser?.organization_name || 'your organization'}, then grant authority separately through Delegations.</p>
      </div>
      {pageError && <div className="alert alert-danger" role="alert">{pageError}</div>}
      <form onSubmit={submit}>
        {drafts.map((draft, index) => {
          const template = templates.find((item) => item.template_id === draft.templateId);
          const locked = draft.status === 'success' || draft.status === 'submitting';
          return (
            <section className="card bg-dark border-secondary mb-3" key={draft.id}>
              <div className="card-header bg-transparent border-secondary d-flex justify-content-between align-items-center">
                <h5 className="mb-0 text-light">Agent {index + 1}</h5>
                {draft.status === 'success' && <span className="badge bg-success">Registered</span>}
              </div>
              <div className="card-body">
                {draft.status === 'failed' && <div className="alert alert-danger py-2">{draft.error}</div>}
                <div className="row g-3">
                  <div className="col-md-6">
                    <label className="form-label text-light">Agent role</label>
                    <select className="form-select bg-dark border-secondary text-light" value={draft.templateId} disabled={locked} onChange={(event) => chooseTemplate(draft, event.target.value)} required>
                      <option value="">Select an agent role...</option>
                      {templates.map((item) => <option key={item.template_id} value={item.template_id}>{item.display_name} ({item.template_version})</option>)}
                    </select>
                  </div>
                  <div className="col-md-6">
                    <label className="form-label text-light">Agent name</label>
                    <input className="form-control bg-dark border-secondary text-light" value={draft.name} disabled={locked} onChange={(event) => updateDraft(draft.id, { name: event.target.value })} required />
                  </div>
                  <div className="col-12">
                    <label className="form-label text-light">Description <span className="text-muted">(optional)</span></label>
                    <textarea className="form-control bg-dark border-secondary text-light" value={draft.description} disabled={locked} onChange={(event) => updateDraft(draft.id, { description: event.target.value })} rows="2" />
                  </div>
                </div>
                {template && (
                  <div className="mt-4">
                    <div className="alert alert-info py-2 small">{template.display_name} actions are available for this role. Authority is granted separately in Delegations.</div>
                    <h6 className="text-light">Available actions</h6>
                    {template.tools.map((tool) => (
                      <div className="list-group-item bg-darker border-secondary d-flex justify-content-between align-items-center gap-3 py-2" key={tool.capability_code}>
                        <div><div className="text-light">{tool.name}</div><div className="text-muted small">{tool.description}</div></div>
                        <span className="badge text-bg-secondary">Supported</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          );
        })}
        <div className="d-flex flex-wrap justify-content-between gap-2">
          <button type="button" className="btn btn-outline-secondary" onClick={() => navigate('/dashboard')}>Back to dashboard</button>
          <div className="d-flex flex-wrap gap-2">
            <button type="button" className="btn btn-outline-info" onClick={() => setDrafts((current) => [...current, makeDraft()])}>Add another agent</button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>{submitting ? 'Registering...' : drafts.some((draft) => draft.status === 'failed') ? 'Retry failed agents' : 'Register agents'}</button>
          </div>
        </div>
      </form>
    </div>
  );
};
