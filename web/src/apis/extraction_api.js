import { apiDelete, apiGet, apiPost, apiPut, apiRequest } from './base'

export const extractionApi = {
  listTemplates: () => apiGet('/api/extraction/templates'),
  createTemplate: (payload) => apiPost('/api/extraction/templates', payload),
  getTemplate: (templateId) => apiGet(`/api/extraction/templates/${templateId}`),
  updateTemplate: (templateId, payload) => apiPut(`/api/extraction/templates/${templateId}`, payload),
  deleteTemplate: (templateId) => apiDelete(`/api/extraction/templates/${templateId}`),
  listBatches: () => apiGet('/api/extraction/batches'),
  createBatch: (payload) => apiPost('/api/extraction/batches', payload),
  createUploadBatch: ({ templateId, kbId, files, modelSpec = null }) => {
    const formData = new FormData()
    formData.append('template_id', templateId)
    formData.append('kb_id', kbId)
    if (modelSpec) formData.append('model_spec', modelSpec)
    files.forEach((file) => formData.append('files', file))
    return apiRequest('/api/extraction/batches/upload', { method: 'POST', body: formData })
  },
  getBatch: (batchId) => apiGet(`/api/extraction/batches/${batchId}`),
  rerunBatch: (batchId) => apiPost(`/api/extraction/batches/${batchId}/rerun`, {}),
  cancelBatch: (batchId) => apiPost(`/api/extraction/batches/${batchId}/cancel`, {}),
  getTask: (taskId) => apiGet(`/api/extraction/tasks/${taskId}`),
  reviseTask: (taskId, payload) => apiPost(`/api/extraction/tasks/${taskId}/revise`, payload),
  exportBatch: (batchId, format = 'json') =>
    apiRequest(`/api/extraction/batches/${batchId}/export?format=${encodeURIComponent(format)}`, {}, true, 'blob')
}
