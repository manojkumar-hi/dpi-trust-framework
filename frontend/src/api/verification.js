import apiClient from './client';

export const verificationApi = {
  verifyVC: async (vcJwt) => {
    const response = await apiClient.post('/credentials/verify', { vc_jwt: vcJwt });
    return response.data;
  }
};
