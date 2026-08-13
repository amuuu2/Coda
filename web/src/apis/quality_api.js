import { apiDelete, apiGet, apiPost } from './base'

/** Agent 质量评测闭环 API。 */
export const qualityApi = {
  listAgents: () => apiGet('/api/agent-quality/agents'),
  listSamples: (agentSlug) => apiGet(`/api/agent-quality/samples?agent_slug=${encodeURIComponent(agentSlug)}`),
  createSample: (payload) => apiPost('/api/agent-quality/samples', payload),
  createSampleFromRun: (runId, expectedOutput = null) => apiPost(`/api/agent-quality/runs/${runId}/sample`, { expected_output: expectedOutput }),
  listCandidates: (agentSlug) => apiGet(`/api/agent-quality/candidates?agent_slug=${encodeURIComponent(agentSlug)}`),
  createCandidate: (payload) => apiPost('/api/agent-quality/candidates', payload),
  createExperiment: (payload) => apiPost('/api/agent-quality/experiments', payload),
  listExperiments: (agentSlug) => apiGet(`/api/agent-quality/experiments?agent_slug=${encodeURIComponent(agentSlug)}`),
  runExperiment: (experimentId) => apiPost(`/api/agent-quality/experiments/${experimentId}/run`, {}),
  getExperiment: (experimentId) => apiGet(`/api/agent-quality/experiments/${experimentId}`),
  deleteExperiment: (experimentId) => apiDelete(`/api/agent-quality/experiments/${experimentId}`),
  approveCandidate: (candidateId) => apiPost(`/api/agent-quality/candidates/${candidateId}/approve`, {}),
  publishCandidate: (candidateId) => apiPost(`/api/agent-quality/candidates/${candidateId}/publish`, {}),
  rollbackCandidate: (candidateId) => apiPost(`/api/agent-quality/candidates/${candidateId}/rollback`, {})
}
