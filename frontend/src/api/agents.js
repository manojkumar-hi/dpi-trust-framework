import apiClient from './client';

export const agentsApi = {
  getAgents: async () => {
    const response = await apiClient.get('/agents');
    return response.data;
  }
};
