import apiClient from './client';

export const auditApi = {
  getAuditRecords: async (limit = 100) => {
    const response = await apiClient.get('/audit', {
      params: { limit }
    });
    return response.data;
  }
};
