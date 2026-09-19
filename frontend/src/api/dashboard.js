import apiClient from './client';

export const dashboardApi = {
  getOrganizations: async () => {
    const response = await apiClient.get('/organizations');
    return response.data;
  },
  getAgents: async () => {
    const response = await apiClient.get('/agents');
    return response.data;
  },
  getCredentials: async () => {
    const response = await apiClient.get('/credentials');
    return response.data;
  },
  getDelegations: async () => {
    const response = await apiClient.get('/delegations');
    return response.data;
  },
  getAuditLogs: async () => {
    const response = await apiClient.get('/audit');
    return response.data;
  }
};
