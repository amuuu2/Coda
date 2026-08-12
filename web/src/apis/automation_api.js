import { apiDelete, apiGet, apiPost, apiPut } from './base'

export const automationApi = {
  listSchedules: () => apiGet('/api/automation/schedules'),
  createSchedule: (payload) => apiPost('/api/automation/schedules', payload),
  getSchedule: (scheduleId) => apiGet(`/api/automation/schedules/${scheduleId}`),
  updateSchedule: (scheduleId, payload) => apiPut(`/api/automation/schedules/${scheduleId}`, payload),
  deleteSchedule: (scheduleId) => apiDelete(`/api/automation/schedules/${scheduleId}`),
  enableSchedule: (scheduleId) => apiPost(`/api/automation/schedules/${scheduleId}/enable`, {}),
  disableSchedule: (scheduleId) => apiPost(`/api/automation/schedules/${scheduleId}/disable`, {}),
  runSchedule: (scheduleId) => apiPost(`/api/automation/schedules/${scheduleId}/run`, {}),
  listRuns: (scheduleId) => apiGet(`/api/automation/schedules/${scheduleId}/runs`),
  getRun: (runId) => apiGet(`/api/automation/runs/${runId}`)
}
