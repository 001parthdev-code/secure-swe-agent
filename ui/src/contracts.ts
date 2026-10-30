export type TaskStatus = 'idle' | 'analyzing' | 'awaiting_change_approval' | 'applying' | 'verifying' | 'awaiting_commit_approval' | 'committed' | 'awaiting_publish_approval' | 'published' | 'rejected' | 'failed' | 'needs_reconciliation';
export type TaskEvent = {id:string; timestamp:string; title:string; detail:string; kind:'success'|'pending'|'info'|'error'};
export type Change = {path:string; before:string; after:string; explanation:string;diff?:string};
export type Task = {id:string; title:string; repository:string; branch:string; status:TaskStatus; model:string; events:TaskEvent[]; changes:Change[]; tests:{passed:number;failed:number;output:string}|null; prUrl:string|null; revision:number};
export interface WorkflowApi {
  getTask():Promise<Task>;
  startTask(description:string):Promise<Task>;
  approveChange(taskId:string, revision:number):Promise<Task>;
  rejectChange(taskId:string, revision:number):Promise<Task>;
  approveCommit(taskId:string, revision:number):Promise<Task>;
  approvePublish(taskId:string, revision:number):Promise<Task>;
}
