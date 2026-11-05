import apiClient from './client';

export const credentialsApi = {
  getCredentials: async (params = {}) => {
    const response = await apiClient.get('/credentials', { params });
    return response.data;
  },
  issueCredential: async (credential) => {
    const response = await apiClient.post('/credentials', credential);
    return response.data;
  },
};
