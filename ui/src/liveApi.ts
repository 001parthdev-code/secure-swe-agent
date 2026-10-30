import type {Task, WorkflowApi} from './contracts';

// Same-origin calls go through the local Vite development proxy. The browser
// never receives the operator token; Vite injects it on the server side.
const endpoint = '/api';
async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(endpoint + path, {
    method,
    headers: {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store',
  });
  const payload: unknown = await response.json();
  if (!response.ok) {
    const message = payload && typeof payload === 'object' && 'detail' in payload
      ? String(payload.detail) : 'Backend request failed';
    throw new Error(message);
  }
  return payload as T;
}
const unavailable = async (): Promise<Task> => {
  throw new Error('Live approval is not enabled yet. No operation was performed.');
};
export const liveApi: WorkflowApi = {
  async getTask() {
    const task = await request<Task | {status: 'no_task'}>('/tasks/current');
    return task.status === 'no_task' ? null as unknown as Task : task as Task;
  },
  startTask(description) { return request<Task>('/tasks', 'POST', {description}); },
  async approveChange(taskId, revision) {
    const current = await request<Task>('/tasks/current');
    if (current.id !== taskId || current.revision !== revision || !current.proposal_sha256)
      throw new Error('Proposal changed; refresh before approving');
    return request<Task>(`/tasks/${encodeURIComponent(taskId)}/approve`, 'POST',
      {revision, proposal_sha256: current.proposal_sha256});
  },
  rejectChange(taskId, revision) {
    return request<Task>(`/tasks/${encodeURIComponent(taskId)}/reject`, 'POST', {revision});
  },
  approveCommit: unavailable,
  approvePublish: unavailable,
};
