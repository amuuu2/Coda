import { apiDelete, apiGet, apiPost, apiPut } from './base'

export const analyticsApi = {
  listDataSources: () => apiGet('/api/analytics/data-sources'),
  createDataSource: (payload) => apiPost('/api/analytics/data-sources', payload),
  getDataSource: (sourceId) => apiGet(`/api/analytics/data-sources/${sourceId}`),
  updateDataSource: (sourceId, payload) => apiPut(`/api/analytics/data-sources/${sourceId}`, payload),
  deleteDataSource: (sourceId) => apiDelete(`/api/analytics/data-sources/${sourceId}`),
  testDataSource: (sourceId) => apiPost(`/api/analytics/data-sources/${sourceId}/test`, {}),
  syncSchema: (sourceId) => apiPost(`/api/analytics/data-sources/${sourceId}/sync-schema`, {}),
  listSchema: (sourceId) => apiGet(`/api/analytics/data-sources/${sourceId}/schema`),
  runQuery: (payload) => apiPost('/api/analytics/queries', payload),
  listQueries: () => apiGet('/api/analytics/queries'),
  getQuery: (queryId) => apiGet(`/api/analytics/queries/${queryId}`)
}
