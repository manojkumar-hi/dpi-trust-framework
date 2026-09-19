import apiClient from './client';

export const delegationsApi = {
  getDelegations: async () => {
    const response = await apiClient.get('/delegations');
    return response.data;
  }
};
