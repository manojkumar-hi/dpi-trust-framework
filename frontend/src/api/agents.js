import apiClient from './client';

export const agentsApi = {
  getAgents: async () => {
    const response = await apiClient.get('/agents');
    return response.data;
  },
  requestAuthorization: async (agentId, delegationId) => {
    const params = delegationId ? { delegation_id: delegationId } : {};
    const response = await apiClient.post(`/agents/${agentId}/simulated-sensitive-op`, null, { params });
    return response.data;
  }
};
