import apiClient from './client';

export const credentialsApi = {
  getCredentials: async () => {
    const response = await apiClient.get('/credentials');
    return response.data;
  }
};
