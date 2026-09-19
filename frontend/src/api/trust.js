import apiClient from './client';

export const trustApi = {
  getTrustScore: async (agentId) => {
    const response = await apiClient.get(`/agents/${agentId}/trust`);
    return response.data;
  }
};
