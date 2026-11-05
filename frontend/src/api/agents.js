import apiClient from './client';

export const agentsApi = {
  getAgents: async (organizationId) => {
    const response = await apiClient.get('/agents', {
      params: organizationId ? { organization_id: organizationId } : undefined
    });
    return response.data;
  },
  getAgent: async (agentId) => {
    const response = await apiClient.get(`/agents/${agentId}`);
    return response.data;
  },
  getAgentIdentity: async (agentId) => {
    const response = await apiClient.get(`/agents/${agentId}/identity`);
    return response.data;
  },
  rekeyIdentity: async (agentId, publicKeyB64) => {
    const response = await apiClient.post(`/agents/${agentId}/identity/rekey`, { public_key_b64: publicKeyB64 });
    return response.data;
  },
  getAgentDidDocument: async (did) => {
    const response = await apiClient.get(`/identities/resolve/${encodeURIComponent(did)}`);
    return response.data;
  },
  getActionHistory: async (agentId) => {
    const response = await apiClient.get(`/agents/${agentId}/actions`);
    return response.data;
  },
  invokeGateway: async (request, idempotencyKey) => {
    const response = await apiClient.post('/gateway/action', request, {
      headers: { 'Idempotency-Key': idempotencyKey }
    });
    return response.data;
  },
  getTemplates: async () => {
    const response = await apiClient.get('/agents/templates');
    return response.data;
  },
  registerFromTemplate: async (registration) => {
    const response = await apiClient.post('/agents/register-template', registration);
    return response.data;
  },
  requestAuthorization: async (agentId, delegationId) => {
    const params = delegationId ? { delegation_id: delegationId } : {};
    const response = await apiClient.post(`/agents/${agentId}/simulated-sensitive-op`, null, { params });
    return response.data;
  }
};
