import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_BACKEND_URL || '/api',
  // 認證採伺服器端 session + HTTP-only cookie，必須帶上 cookie 才能維持登入狀態。
  withCredentials: true,
});

const uploadTimeoutMs = Number(import.meta.env.VITE_UPLOAD_TIMEOUT_MS || 600000);

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

// ── Auth ─────────────────────────────────────────────────────
export interface Administrator {
  id: string;
  username: string;
  is_active: boolean;
  created_at: string;
}

export const getCurrentAdministrator = (): Promise<Administrator> => get('/auth/me');
export const login = (username: string, password: string): Promise<Administrator> =>
  post('/auth/login', { username, password });
export const logout = (): Promise<{ message: string }> => post('/auth/logout');

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
    timeout: uploadTimeoutMs
  });
};

export const listDocuments = (projectId: string) =>
  get(`/projects/${projectId}/documents`);

// ── Chat ─────────────────────────────────────────────────────
// agent=true 走自主 tool-calling 的 /agent-chat（LLM 自行決定要不要查/查什麼/查幾次/用哪種策略）；
// agent=false 走固定流程 /chat。兩者回應 shape 相同。
export const chat = (projectId: string, question: string, top_k: number = 5, agent: boolean = false) =>
  post(`/projects/${projectId}/${agent ? 'agent-chat' : 'chat'}`, { question, top_k });

// ── Observability ────────────────────────────────────────────
export const listAgentRuns = (projectId: string, limit: number = 50) =>
  get(`/projects/${projectId}/agent-runs`, { params: { limit } });

export const listToolCalls = (agentRunId: string) =>
  get(`/agent-runs/${agentRunId}/tool-calls`);

// ── Guided Workflows ─────────────────────────────────────────
export const getWorkflowStatus = (projectId: string) =>
  get(`/projects/${projectId}/workflow-status`);

export default api;
