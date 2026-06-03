import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_BACKEND_URL || '/api',
});

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    let detail = error.response?.data?.detail || error.response?.data || error.message;
    return Promise.reject(new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)));
  }
);

// Helper to bypass AxiosResponse type inference
const get = async (url: string, config?: any): Promise<any> => api.get(url, config);
const post = async (url: string, data?: any, config?: any): Promise<any> => api.post(url, data, config);

// ── Projects ─────────────────────────────────────────────────
export const listProjects = () => get('/projects/');
export const createProject = (name: string, description?: string) => 
  post('/projects/', { name, description });

// ── Upload ───────────────────────────────────────────────────
export const uploadDocument = (projectId: string, file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return post(`/projects/${projectId}/upload/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000
  });
};

export const uploadTickets = (projectId: string, file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return post(`/projects/${projectId}/upload/tickets`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  });
};

export const listDocuments = (projectId: string) =>
  get(`/projects/${projectId}/documents`);

// ── Chat & Analysis ──────────────────────────────────────────
export const chat = (projectId: string, question: string, top_k: number = 5) => 
  post(`/projects/${projectId}/chat`, { question, top_k });

export const analyzeIncidents = (projectId: string) => 
  post(`/projects/${projectId}/analyze/incidents`, null, { timeout: 600000 });

// ── Dashboard / Observability ────────────────────────────────
export const getDashboard = (projectId: string) => 
  get(`/projects/${projectId}/dashboard`);

export const listAgentRuns = (projectId: string, limit: number = 50) => 
  get(`/projects/${projectId}/agent-runs`, { params: { limit } });

export const listToolCalls = (agentRunId: string) => 
  get(`/agent-runs/${agentRunId}/tool-calls`);

export default api;
