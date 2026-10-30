import type {Task, TaskEvent, WorkflowApi} from './contracts';
const stamp=()=>new Date().toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',hour12:false});
const event=(title:string,detail:string,kind:TaskEvent['kind']='success'):TaskEvent=>({id:crypto.randomUUID(),timestamp:stamp(),title,detail,kind});
const initial:Task={id:'DEMO-001',title:'Fix the subtraction bug without changing other operations',repository:'calculator-demo',branch:'agent/task-fix-subtraction',status:'awaiting_change_approval',model:'qwen3.5:4b',revision:1,tests:null,prUrl:null,events:[event('Repository analyzed','3 approved files inspected through the Enforcer'),event('Issue identified','subtract(8, 3) returned 11 instead of 5'),event('Patch proposed','One file ready for human review','pending')],changes:[{path:'calculator/calculator.py',before:'    # Intentional bug for the agent to discover and correct.\n    return a + b',after:'    # Fixed subtraction operation.\n    return a - b',explanation:'Replace addition with subtraction while preserving other arithmetic operations.'}]};
let task:Task=structuredClone(initial);
const wait=()=>new Promise(r=>setTimeout(r,240));
const snapshot=()=>structuredClone(task);
const assertRevision=(id:string,rev:number,allowed:Task['status'])=>{if(task.id!==id||task.revision!==rev||task.status!==allowed)throw new Error('Task state changed. Refresh before approving.');};
const advance=(status:Task['status'],title:string,detail:string,kind:TaskEvent['kind']='success')=>{task={...task,status,revision:task.revision+1,events:[...task.events,event(title,detail,kind)]};return snapshot();};
export const mockApi:WorkflowApi={
  async getTask(){await wait();return snapshot()},
  async startTask(description){await wait();if(!description.trim())throw new Error('Enter a task description.');if(!/subtract|subtraction/i.test(description))throw new Error('This mock supports only the calculator subtraction scenario. No real agent is running.');task={...structuredClone(initial),id:'DEMO-'+Math.floor(100+Math.random()*900),title:description.trim(),revision:1};return snapshot()},
  async approveChange(id,rev){await wait();assertRevision(id,rev,'awaiting_change_approval');task.tests={passed:6,failed:0,output:'Ran 6 tests in 0.006s — OK'};return advance('awaiting_commit_approval','Simulated change and verification','Mock transition · 6 simulated tests passed','pending')},
  async rejectChange(id,rev){await wait();assertRevision(id,rev,'awaiting_change_approval');return advance('rejected','Change rejected','No files were modified','error')},
  async approveCommit(id,rev){await wait();assertRevision(id,rev,'awaiting_commit_approval');return advance('awaiting_publish_approval','Simulated commit','No Git commit was created by this UI','pending')},
  async approvePublish(id,rev){await wait();assertRevision(id,rev,'awaiting_publish_approval');task.prUrl='https://github.com/001parthdev-code/secure-swe-agent-demo/pull/1';return advance('published','Simulated publication','Historical PR link shown; no new PR was created')}
};
