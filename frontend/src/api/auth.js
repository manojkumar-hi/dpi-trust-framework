import apiClient from './client';

export const authApi = {
  register: async (registration) => {
    const response = await apiClient.post('/auth/register', registration);
    return response.data;
  },
  login: async (credentials) => {
    const response = await apiClient.post('/auth/login', credentials);
    return response.data;
  },
  logout: async () => {
    await apiClient.post('/auth/logout');
  },
  currentUser: async () => {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },
  completeOnboarding: async () => {
    const response = await apiClient.post('/auth/onboarding/complete');
    return response.data;
  }
};
