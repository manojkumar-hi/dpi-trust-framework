import apiClient from './client';

export const dashboardApi = {
  getOrganizations: async (organizationId) => {
    const response = await apiClient.get('/organizations');
    return response.data.filter((organization) => !organizationId || organization.id === organizationId);
  },
  getAgents: async () => {
    const response = await apiClient.get('/agents');
    return response.data;
  },
  getCredentials: async (organizationId) => {
    const response = await apiClient.get('/credentials');
    return response.data.filter((credential) => !organizationId || credential.issuer_organization_id === organizationId);
  },
  getDelegations: async (organizationId) => {
    const response = await apiClient.get('/delegations');
    return response.data.filter((delegation) => !organizationId || delegation.delegator_organization_id === organizationId);
  },
  getAuditLogs: async () => {
    const response = await apiClient.get('/audit');
    return response.data;
  }
};
