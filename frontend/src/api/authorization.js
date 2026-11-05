import apiClient from './client';

export const authorizationApi = {
  preCheck: async ({ agentId, actionType, delegationId }) => {
    const response = await apiClient.post('/authorization/pre-check', {
      agent_id: agentId,
      action_type: actionType,
      delegation_id: delegationId || null,
    });
    return response.data;
  },
};
