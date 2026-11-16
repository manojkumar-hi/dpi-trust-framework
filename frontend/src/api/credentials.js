import apiClient from './client';

export const credentialsApi = {
  getCredentials: async (params = {}, organizationId = null) => {
    const response = await apiClient.get('/credentials', { params });
    return response.data.filter((credential) => (
      !organizationId || credential.issuer_organization_id === organizationId
    ));
  },
  issueCredential: async (credential) => {
    const response = await apiClient.post('/credentials', credential);
    return response.data;
  },
};
