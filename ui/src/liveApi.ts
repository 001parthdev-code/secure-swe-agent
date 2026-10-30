import type {Task, WorkflowApi} from './contracts';
const endpoint = '/api';
const token = import.meta.env.VITE_SWE_OPERATOR_TOKEN as string | undefined;
function headers(): HeadersInit {
  return {'Content-Type':'application/json','X-Operator-Token':token ?? ''};
}
async function request<T>(path:string, method='GET', body?:unknown):Promise<T> {
  const response = await fetch(endpoint+path,{method,headers:headers(),body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});
  const payload:unknown = await response.json();
  if (!response.ok) {
    const message = (payload && typeof payload==='object' && 'detail' in payload) ? String(payload.detail) : 'Backend request failed';
    throw new Error(message);
  }
  return payload as T;
}
const unavailable = async ():Promise<Task> => {throw new Error('Live approval is not enabled yet. No operation was performed.');};
export const liveApi:WorkflowApi = {
  async getTask(){const task=await request<Task|{status:'no_task'}>('/tasks/current');return task.status==='no_task'?null as unknown as Task:task as Task;},
  startTask(description){return request<Task>('/tasks','POST',{description});},
  approveChange:unavailable, rejectChange:unavailable, approveCommit:unavailable, approvePublish:unavailable,
};
