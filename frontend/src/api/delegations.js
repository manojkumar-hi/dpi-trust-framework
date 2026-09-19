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
  getDelegationChain: async (delegationId) => {
    const response = await apiClient.get(`/delegations/${delegationId}/chain`);
    return response.data;
  }
};
