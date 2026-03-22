const BASE = '/intellintents/api';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    let message = text;
    try {
      const json = JSON.parse(text);
      if (json.detail) message = json.detail;
    } catch {}
    throw new Error(message);
  }
  return res.json();
}

// Seed demo data
export const seedDemo = () => request('/seed-demo', { method: 'POST' });

// Datasets
export const getDatasets = () => request('/datasets');
export const createDataset = (data) => request('/datasets', { method: 'POST', body: JSON.stringify(data) });
export const uploadDataset = async (file, name, description) => {
  const formData = new FormData();
  formData.append('file', file);
  if (name) formData.append('name', name);
  if (description) formData.append('description', description);
  const res = await fetch(`${BASE}/datasets/upload`, { method: 'POST', body: formData });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
};
export const loadDatasetFromSource = (source, name, description) =>
  request('/datasets/load-source', { method: 'POST', body: JSON.stringify({ source, name, description }) });
export const getDataset = (id) => request(`/datasets/${id}`);
export const getConversations = (datasetId) => request(`/datasets/${datasetId}/conversations`);
export const getConversation = (datasetId, convId) => request(`/datasets/${datasetId}/conversations/${convId}`);
export const deleteDataset = (id) => request(`/datasets/${id}`, { method: 'DELETE' });
export const getDatasetRuns = (datasetId) => request(`/datasets/${datasetId}/runs`);

// Taxonomies
export const getTaxonomies = () => request('/taxonomies');
export const createTaxonomy = (data) => request('/taxonomies', { method: 'POST', body: JSON.stringify(data) });
export const getTaxonomy = (id) => request(`/taxonomies/${id}`);
export const updateTaxonomy = (id, data) => request(`/taxonomies/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteTaxonomy = (id) => request(`/taxonomies/${id}`, { method: 'DELETE' });
export const addCategory = (taxonomyId, data) => request(`/taxonomies/${taxonomyId}/categories`, { method: 'POST', body: JSON.stringify(data) });
export const updateCategory = (taxonomyId, categoryId, data) => request(`/taxonomies/${taxonomyId}/categories/${categoryId}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteCategory = (taxonomyId, categoryId) => request(`/taxonomies/${taxonomyId}/categories/${categoryId}`, { method: 'DELETE' });
export const moveCategory = (taxonomyId, categoryId, newParentId) => request(`/taxonomies/${taxonomyId}/categories/${categoryId}/move`, { method: 'PUT', body: JSON.stringify({ new_parent_id: newParentId }) });
export const reorderCategories = (taxonomyId, categoryIds) => request(`/taxonomies/${taxonomyId}/categories/reorder`, { method: 'PUT', body: JSON.stringify({ category_ids: categoryIds }) });
export const setCategoryExamples = (taxonomyId, categoryId, examples) => request(`/taxonomies/${taxonomyId}/categories/${categoryId}/examples`, { method: 'PUT', body: JSON.stringify({ examples }) });
export const clearCategoryExamples = (taxonomyId, categoryId) => request(`/taxonomies/${taxonomyId}/categories/${categoryId}/examples`, { method: 'DELETE' });
export const importTaxonomy = (data) => request('/taxonomies/import', { method: 'POST', body: JSON.stringify(data) });
export const importTaxonomyFromSource = (source) =>
  request('/taxonomies/import-source', { method: 'POST', body: JSON.stringify({ source }) });
export const exportTaxonomy = (id) => request(`/taxonomies/${id}/export`);

// Classification
export const classify = (data) => request('/classify', { method: 'POST', body: JSON.stringify(data) });
export const getClassifyMethods = () => request('/classify/methods');
export const getClassifyResults = (datasetId, taxonomyId) => request(`/classify/results/${datasetId}/${taxonomyId}`);

// Analytics
export const getAnalyticsSummary = (datasetId) => request(`/analytics/summary/${datasetId}`);
export const getAnalyticsDistribution = (datasetId, taxonomyId) => request(`/analytics/distribution/${datasetId}/${taxonomyId}`);
export const getAnalyticsTransitions = (datasetId, taxonomyId) => request(`/analytics/transitions/${datasetId}/${taxonomyId}`);
export const getAnalyticsHeatmap = (datasetId, taxonomyId) => request(`/analytics/heatmap/${datasetId}/${taxonomyId}`);
export const getConversationGraph = (conversationId) => request(`/analytics/graph/${conversationId}`);

// Turn Search
export const searchTurns = (datasetId, params = {}) => {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v != null && v !== '') {
      if (Array.isArray(v)) v.forEach(item => qs.append(k, item));
      else qs.append(k, v);
    }
  });
  return request(`/datasets/${datasetId}/turns/search?${qs}`);
};
export const getTurnFilterOptions = (datasetId, taxonomyId, runId) => {
  const qs = new URLSearchParams();
  if (taxonomyId) qs.append('taxonomy_id', taxonomyId);
  if (runId) qs.append('run_id', runId);
  const qsStr = qs.toString();
  return request(`/datasets/${datasetId}/turns/filter-options${qsStr ? '?' + qsStr : ''}`);
};

// Experiments
export const getExperiments = () => request('/experiments');
export const createExperiment = (data) => request('/experiments', { method: 'POST', body: JSON.stringify(data) });
export const getExperiment = (id) => request(`/experiments/${id}`);
export const updateExperiment = (id, data) => request(`/experiments/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteExperiment = (id) => request(`/experiments/${id}`, { method: 'DELETE' });
export const runExperiment = (id) => request(`/experiments/${id}/run`, { method: 'POST' });
export const getExperimentRuns = (id) => request(`/experiments/${id}/runs`);
export const getRun = (runId) => request(`/experiments/runs/${runId}`);
export const getRunResults = (runId) => request(`/experiments/runs/${runId}/results`);
export const deleteRun = (runId) => request(`/experiments/runs/${runId}`, { method: 'DELETE' });
export const getExperimentLabelMapping = (id) => request(`/experiments/${id}/label-mapping`);
export const setExperimentLabelMapping = (id, mappings) => request(`/experiments/${id}/label-mapping`, { method: 'POST', body: JSON.stringify(mappings) });
export const validateExperimentLabels = (id) => request(`/experiments/${id}/validate-labels`);
