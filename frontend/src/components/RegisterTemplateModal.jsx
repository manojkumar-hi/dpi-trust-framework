import React, { useEffect, useState } from 'react';
import { agentsApi } from '../api/agents';
import { useAuth } from '../context/AuthContext';

export const RegisterTemplateModal = ({ onClose, onSuccess }) => {
  const { orgId } = useAuth();
  const [templates, setTemplates] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [registration, setRegistration] = useState(null);

  useEffect(() => {
    agentsApi.getTemplates()
      .then((availableTemplates) => {
        setTemplates(availableTemplates);
        if (availableTemplates.length > 0) {
          const firstTemplate = availableTemplates[0];
          setSelectedTemplateId(firstTemplate.template_id);
        }
      })
      .catch(() => setError('Failed to load available agent roles.'));
  }, []);

  const selectedTemplate = templates.find((template) => template.template_id === selectedTemplateId);

  const submit = async (event) => {
    event.preventDefault();
    if (!selectedTemplate || !name.trim()) {
      setError('Choose an agent role and provide an agent name.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const createdAgent = await agentsApi.registerFromTemplate({
        organization_id: orgId,
        name: name.trim(),
        description: description.trim() || `${selectedTemplate.display_name} agent`,
        template_id: selectedTemplate.template_id,
        template_version: selectedTemplate.template_version,
      });
      setRegistration(createdAgent);
      onSuccess(createdAgent);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to register the agent.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center" style={{ backgroundColor: 'rgba(0,0,0,0.7)', zIndex: 1050 }}>
      <div className="card bg-dark border-secondary shadow-lg w-100" style={{ maxWidth: '650px', maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="card-header border-secondary d-flex justify-content-between align-items-center bg-transparent py-3">
          <h5 className="mb-0 text-light">Register Agent</h5>
          <button className="btn-close btn-close-white" onClick={onClose} aria-label="Close"></button>
        </div>
        <div className="card-body">
          {error && <div className="alert alert-danger py-2">{error}</div>}
          {registration ? (
            <>
              <div className="alert alert-success">Agent registered successfully.</div>
              <dl className="row small mb-4">
                <dt className="col-sm-4">Agent</dt><dd className="col-sm-8">{registration.name}</dd>
                <dt className="col-sm-4">Role</dt><dd className="col-sm-8">{selectedTemplate?.display_name}</dd>
              </dl>
              <div className="alert alert-info small">Registration creates the agent identity. No authority has been granted yet. Use Delegations to grant specific actions.</div>
              <h6 className="text-light">Available actions</h6>
              <div className="list-group mb-3">
                {(selectedTemplate?.tools || []).map((tool) => <div key={tool.capability_code} className="list-group-item bg-darker border-secondary"><div className="text-light fw-bold">{tool.name.replaceAll('_', ' ')}</div><div className="text-muted small">{tool.description}</div></div>)}
              </div>
              <div className="d-flex justify-content-end"><button type="button" className="btn btn-primary" onClick={onClose}>Done</button></div>
            </>
          ) : (
          <form onSubmit={submit}>
            <div className="mb-3">
              <label className="form-label text-light">Agent role</label>
              <select className="form-select bg-dark border-secondary text-light" value={selectedTemplateId} onChange={(event) => {
                setSelectedTemplateId(event.target.value);
              }} required>
                <option value="">Select an agent role...</option>
                {templates.map((template) => <option key={template.template_id} value={template.template_id}>{template.display_name} ({template.template_version})</option>)}
              </select>
            </div>
            <div className="mb-3">
              <label className="form-label text-light">Agent name</label>
              <input className="form-control bg-dark border-secondary text-light" value={name} onChange={(event) => setName(event.target.value)} required />
            </div>
            <div className="mb-3">
              <label className="form-label text-light">Description</label>
              <textarea className="form-control bg-dark border-secondary text-light" value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Describe this agent's purpose" rows="2" />
            </div>
            {selectedTemplate && (
              <div className="mb-4">
                <div className="alert alert-info py-2 small">{selectedTemplate.description}</div>
                <label className="form-label text-light">Available actions</label>
                <p className="text-muted small">These actions are supported by the selected role. Authority is granted separately in Delegations.</p>
                <div className="list-group">
                  {selectedTemplate.tools.map((tool) => (
                    <div key={tool.capability_code} className="list-group-item bg-darker border-secondary">
                      <div className="text-light fw-bold">{tool.name.replaceAll('_', ' ')}</div>
                      <div className="text-muted small">{tool.description}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="d-flex justify-content-end gap-2">
              <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={loading}>{loading ? 'Registering...' : 'Register Agent'}</button>
            </div>
          </form>
          )}
        </div>
      </div>
    </div>
  );
};
