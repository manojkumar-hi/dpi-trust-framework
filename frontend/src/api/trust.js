import apiClient from './client';

export const trustApi = {
  getTrustScore: async (agentId) => {
    const response = await apiClient.get(`/agents/${agentId}/trust`);
    return response.data;
  },
  submitEvidence: async (agentId, evidencePayload, idempotencyKey) => {
    const headers = idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {};
    const response = await apiClient.post(`/agents/${agentId}/trust/evidence`, evidencePayload, { headers });
    return response.data;
  }
};
