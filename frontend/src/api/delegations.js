import apiClient from './client';

export const delegationsApi = {
  getDelegations: async () => {
    const response = await apiClient.get('/delegations');
    return response.data;
  },
  verifyDelegation: async (delegationId) => {
    const response = await apiClient.get(`/delegations/${delegationId}/verify`);
    return response.data;
  },
  getDelegation: async (delegationId) => {
    const response = await apiClient.get(`/delegations/${delegationId}`);
    return response.data;
  },
  getDelegationChain: async (delegationId) => {
    const response = await apiClient.get(`/delegations/${delegationId}/chain`);
    return response.data;
  },
  revokeDelegation: async (delegationId, reason) => {
    const response = await apiClient.post(`/delegations/${delegationId}/revoke`, { reason });
    return response.data;
  },
  createDelegation: async (delegationData) => {
    const response = await apiClient.post('/delegations', delegationData);
    return response.data;
  }
};
