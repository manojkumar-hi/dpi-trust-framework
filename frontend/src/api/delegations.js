import apiClient from './client';

export const delegationsApi = {
  getDelegations: async (organizationId = null) => {
    const response = await apiClient.get('/delegations');
    return response.data.filter((delegation) => (
      !organizationId || delegation.delegator_organization_id === organizationId
    ));
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
