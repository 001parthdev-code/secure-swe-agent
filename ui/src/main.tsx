import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, AlertTriangle, ArrowUpRight, Check, CheckCircle2, ChevronRight, Circle, ClipboardCheck, Code2, FileCode2, FolderGit2, GitBranch, GitCommitHorizontal, GitPullRequest, LayoutDashboard, LockKeyhole, Play, RefreshCcw, RotateCcw, ShieldCheck, TerminalSquare, X, XCircle } from 'lucide-react';
import { DiffReview } from './DiffReview';
import type { Task, TaskStatus, WorkflowApi } from './contracts';
import { mockApi } from './mockApi';
import './styles.css';

const api: WorkflowApi = mockApi;
type Section = 'workspace' | 'activity' | 'review';
type ReviewTab = 'diff' | 'tests';
type Decision = 'change' | 'commit' | 'publish' | 'reject';
const statuses: Record<TaskStatus,string> = {idle:'Idle',analyzing:'Analyzing',awaiting_change_approval:'Change review',applying:'Applying change',verifying:'Verifying',awaiting_commit_approval:'Commit review',committed:'Committed',awaiting_publish_approval:'Publish review',published:'Published (simulated)',rejected:'Rejected',failed:'Failed',needs_reconciliation:'Needs reconciliation'};
const steps = [
  { label: 'Analyze', detail: 'Inspect repository', icon: Code2 },
  { label: 'Change review', detail: 'Approve exact patch', icon: FileCode2 },
  { label: 'Verification', detail: 'Run trusted tests', icon: ClipboardCheck },
  { label: 'Commit review', detail: 'Approve staged diff', icon: GitCommitHorizontal },
  { label: 'Publication', detail: 'Approve GitHub PR', icon: GitPullRequest },
];
function stage(status: TaskStatus): number {
  if (status==='idle'||status==='analyzing') return 0;
  if (status==='awaiting_change_approval'||status==='rejected') return 1;
  if (status==='applying'||status==='verifying') return 2;
  if (status==='awaiting_commit_approval') return 3;
  return 4;
}
function App() {
  const [task,setTask]=useState<Task|null>(null);
  const [draft,setDraft]=useState('Fix the subtraction bug without changing other arithmetic operations.');
  const [section,setSection]=useState<Section>('workspace');
  const [tab,setTab]=useState<ReviewTab>('diff');
  const [decision,setDecision]=useState<Decision|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  useEffect(()=>{void api.getTask().then(setTask).catch(e=>setError(String(e)))},[]);
  async function run(action:()=>Promise<Task>,message:string) {
    setBusy(true);setError('');setNotice('');
    try { const next=await action();setTask(next);setNotice(message);setDecision(null); }
    catch(e){setError(e instanceof Error?e.message:String(e));setDecision(null)}
    finally{setBusy(false)}
  }
  const status=task?.status;
  const current=task?stage(task.status):0;
  const actionable=status==='awaiting_change_approval'||status==='awaiting_commit_approval'||status==='awaiting_publish_approval';
  function decide() {
    if(!task||!decision)return;
    const id=task.id,rev=task.revision;
    const action:Record<Decision,()=>Promise<Task>>={
      change:()=>api.approveChange(id,rev),commit:()=>api.approveCommit(id,rev),publish:()=>api.approvePublish(id,rev),reject:()=>api.rejectChange(id,rev)
    };
    const messages:Record<Decision,string>={change:'Mock change approved. Simulated verification complete.',commit:'Mock commit approval recorded.',publish:'Mock publication complete. No PR was created.',reject:'Mock proposal rejected. No files were modified.'};
    void run(action[decision],messages[decision]);
  }
  const reviewTitle=decision==='change'?'Approve proposed code change?':decision==='commit'?'Approve simulated Git commit?':decision==='publish'?'Approve simulated GitHub publication?':'Reject proposed change?';
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brandIcon"><ShieldCheck size={21}/></div><div><strong>SECURE SWE</strong><span>AGENT WORKSPACE</span></div></div>
      <div className="sideLabel">WORKSPACE</div>
      <nav aria-label="Main navigation">
        <button className={section==='workspace'?'navActive':''} onClick={()=>setSection('workspace')}><LayoutDashboard size={17}/> Overview</button>
        <button className={section==='activity'?'navActive':''} onClick={()=>setSection('activity')}><Activity size={17}/> Task activity</button>
        <button className={section==='review'?'navActive':''} onClick={()=>{setSection('review');setTab('diff')}}><GitPullRequest size={17}/> Review & publish</button>
      </nav>
      <div className="sideLabel second">ENVIRONMENT</div>
      <div className="environment"><span className="dot"/> Mock workflow · Offline</div>
      <div className="sideBottom"><LockKeyhole size={17}/><span>Frontend-only preview<br/><small>No Enforcer or GitHub access</small></span></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="crumb">Workspace <ChevronRight size={13}/> {section==='workspace'?'Overview':section==='activity'?'Task activity':'Review & publish'}</div><div className="topright"><span className="mode">SIMULATION MODE</span><span className="avatar">UI</span></div></header>
      <div className="content">
        <div className="eyebrow">SECURE SOFTWARE ENGINEERING <span className="eyebrowLine"/></div>
        <div className="headline"><div><h1>{section==='workspace'?'Agent workspace':section==='activity'?'Execution activity':'Review center'}</h1><p>{section==='workspace'?'Inspect a supervised coding workflow, from task to pull request.':section==='activity'?'A transparent timeline of simulated agent operations.':'Review changes, verification evidence, and publication checkpoints.'}</p></div><button className="outline" disabled={busy} onClick={()=>void run(()=>api.getTask(),'Task refreshed.')}><RefreshCcw size={15}/> Refresh</button></div>
        <div className="noticeBanner"><AlertTriangle size={17}/><span><strong>Demo environment.</strong> All operations below are simulated. No code is modified, no tests are executed, and no new GitHub PR is created.</span></div>
        <div className="stats">
          <div className="stat"><span>MODEL</span><strong>Qwen 3.5 · 4B</strong><small>Reference configuration · offline</small></div>
          <div className="stat"><span>ENFORCEMENT</span><strong><ShieldCheck size={18}/> Rust Enforcer</strong><small>Not connected to this preview</small></div>
          <div className="stat"><span>WORKFLOW</span><strong>Supervised</strong><small>Three approval checkpoints</small></div>
        </div>
        <section className="panel journeyPanel" aria-label="Workflow stages"><div className="journeyHeader"><span className="sectionIndex">WORKFLOW OVERVIEW</span><span className="taskId">{task?.id??'Loading task...'}</span></div><div className="journey">{steps.map((s,i)=>{const Icon=s.icon;const done=!!task&&(i<current||task.status==='published');const active=!!task&&i===current&&task.status!=='published';return <div className={'journeyStep '+(done?'done ':active?'active ':'')} key={s.label}><div className="journeyIcon">{done?<Check size={16}/>:<Icon size={16}/>}</div><div><strong>{s.label}</strong><small>{s.detail}</small></div></div>})}</div></section>
        {section==='workspace'&&<section className="panel taskPanel"><div className="panelHead"><div><span className="sectionIndex">01 / TASK</span><h2>What should the agent do?</h2></div><span className="mutedPill"><FolderGit2 size={14}/> calculator-demo · fixed fixture</span></div><label className="inputLabel" htmlFor="task-description">Task description</label><textarea id="task-description" value={draft} maxLength={1200} onChange={e=>setDraft(e.target.value)} placeholder="Describe the calculator subtraction task..."/><div className="taskFoot"><span><LockKeyhole size={14}/> Fixed calculator fixture · mock only</span><button className="primaryBtn" disabled={busy||!draft.trim()} onClick={()=>void run(()=>api.startTask(draft),'New simulated task prepared.')}><Play size={15}/> Start new simulation</button></div></section>}
        <div className="columns"><div className="primary">
          {(section!=='activity')&&<section className="panel changesPanel"><div className="panelHead"><div><span className="sectionIndex">02 / REVIEW</span><h2>Code & verification</h2></div><div className="tabs" role="tablist" aria-label="Review content"><button role="tab" aria-selected={tab==='diff'} className={tab==='diff'?'active':''} onClick={()=>setTab('diff')}>Code diff</button><button role="tab" aria-selected={tab==='tests'} className={tab==='tests'?'active':''} onClick={()=>setTab('tests')}>Tests</button></div></div>
            {tab==='diff'?<><div className="fileBar"><FileCode2 size={17}/><span>{task?.changes[0]?.path??'No file selected'}</span><span className="fileCount">{task?.changes.length??0} file</span></div><DiffReview change={task?.changes[0]}/><p className="explanation">{task?.changes[0]?.explanation??'No change proposal available.'}</p></>:<div className="testBox">{task?.tests?<><div className="passed"><CheckCircle2 size={18}/>{task.tests.passed} simulated passed · {task.tests.failed} simulated failed</div><pre>{task.tests.output}</pre></>:<div className="empty"><TerminalSquare size={20}/> Simulated test results appear after change approval.</div>}</div>}
            {status==='awaiting_change_approval'&&<div className="reviewActions"><button className="outline danger" disabled={busy} onClick={()=>setDecision('reject')}><XCircle size={15}/> Reject</button><button className="primaryBtn" disabled={busy} onClick={()=>setDecision('change')}><Check size={16}/> Review approval</button></div>}
            {status==='awaiting_commit_approval'&&<div className="reviewActions"><span className="inlineSuccess"><CheckCircle2 size={16}/> Simulated tests passed</span><button className="primaryBtn" disabled={busy} onClick={()=>setDecision('commit')}>Review commit approval</button></div>}
            {status==='awaiting_publish_approval'&&<div className="reviewActions"><span className="quiet">Target: demo repository · main</span><button className="primaryBtn" disabled={busy} onClick={()=>setDecision('publish')}>Review publication</button></div>}
            {status==='published'&&<div className="reviewActions"><span className="inlineSuccess"><CheckCircle2 size={16}/> Simulation complete</span><a className="prLink" href={task?.prUrl??'#'} target="_blank" rel="noreferrer">Historical example PR <ArrowUpRight size={15}/></a></div>}
            {status==='rejected'&&<div className="reviewActions"><span className="quiet">Proposal rejected · No files changed</span><button className="outline" onClick={()=>void run(()=>api.startTask(draft),'Simulation restarted.')} disabled={busy}><RotateCcw size={15}/> Restart</button></div>}
          </section>}
          {section==='activity'&&<section className="panel activityFull"><div className="panelHead"><div><span className="sectionIndex">FULL EVENT LOG</span><h2>Workflow timeline</h2></div><Activity size={18}/></div><Timeline task={task}/></section>}
          {section==='review'&&<section className="panel publishPanel"><div className="panelHead"><div><span className="sectionIndex">03 / PUBLICATION</span><h2>GitHub destination</h2></div><GitPullRequest size={18}/></div><div className="publishDetails"><div><span>Repository</span><strong>001parthdev-code/secure-swe-agent-demo</strong></div><div><span>Base branch</span><strong>main</strong></div><div><span>Task branch</span><strong>{task?.branch??'—'}</strong></div><div><span>Publication</span><strong>{status==='published'?'Simulated completion':'Not published by this UI'}</strong></div></div></section>}
        </div><div className="secondary"><section className="panel statusPanel"><div className="panelHead"><div><span className="sectionIndex">TASK STATUS</span><h2>Current state</h2></div><span className="liveDot"/></div><div className="taskId">{task?.id??'Loading...'}</div><div className="statusBadge"><span className="dot"/>{task?statuses[task.status]:'Loading'}</div><div className="divider"/><div className="metadata"><span><GitBranch size={15}/> Branch</span><strong>{task?.branch??'—'}</strong></div><div className="metadata"><span><Code2 size={15}/> Repository</span><strong>{task?.repository??'—'}</strong></div><div className="metadata"><span><LockKeyhole size={15}/> Checkpoint</span><strong>{actionable?'Human approval':'None pending'}</strong></div></section>{section!=='activity'&&<section className="panel activityPanel"><div className="panelHead"><div><span className="sectionIndex">EVENT LOG</span><h2>Recent activity</h2></div><button className="textButton" onClick={()=>setSection('activity')}>View all <ArrowUpRight size={14}/></button></div><Timeline task={task} limit={4}/></section>}<section className="panel helperPanel"><span className="sectionIndex">SECURITY BOUNDARY</span><div className="helperTitle"><ShieldCheck size={19}/> Approvals stay server-side</div><p>In production, the backend will verify the exact proposal, task revision, and permissions. This preview never sends an authorization request.</p></section></div></div>
        {error&&<div className="error" role="alert"><AlertTriangle size={17}/>{error}<button aria-label="Dismiss error" onClick={()=>setError('')}><X size={15}/></button></div>}
        {notice&&<div className="toast" role="status"><CheckCircle2 size={16}/>{notice}<button aria-label="Dismiss notice" onClick={()=>setNotice('')}><X size={14}/></button></div>}
        <footer>SECURE SWE AGENT <span>·</span> FRONTEND PREVIEW <span>·</span> MOCK DATA — NO REAL OPERATIONS</footer>
      </div>
    </main>
    {decision&&task&&<div className="modalBackdrop" onMouseDown={e=>{if(e.target===e.currentTarget&&!busy)setDecision(null)}}><div className="modal" role="dialog" aria-modal="true" aria-labelledby="decision-title"><div className="modalTop"><div className="modalIcon"><LockKeyhole size={20}/></div><button className="iconButton" aria-label="Close approval dialog" disabled={busy} onClick={()=>setDecision(null)}><X size={18}/></button></div><h2 id="decision-title">{reviewTitle}</h2><p>This is a simulation. The action will update only in-memory demo state. No file, Git commit, or pull request will be created.</p><div className="approvalFacts"><div><span>Task</span><strong>{task.id}</strong></div><div><span>Revision</span><strong>{task.revision}</strong></div><div><span>Repository</span><strong>{task.repository}</strong></div><div><span>Operation</span><strong>{decision}</strong></div></div><div className="modalActions"><button className="outline" disabled={busy} onClick={()=>setDecision(null)}>Cancel</button><button className={'primaryBtn '+(decision==='reject'?'rejectBtn':'')} disabled={busy} onClick={decide}>{busy?'Working...':decision==='reject'?'Reject simulation':'Confirm simulated approval'}</button></div></div></div>}
  </div>;
}
function Timeline({task,limit}:{task:Task|null;limit?:number}){const events=limit?task?.events.slice(-limit):task?.events;return <div className="timeline">{events?.length?events.map((e,i)=><div className="event" key={e.id}><div className={'eventIcon '+e.kind}>{e.kind==='error'?<XCircle size={14}/>:e.kind==='pending'?<Circle size={13}/>:<Check size={14}/>}</div><div><strong>{e.title}</strong><p>{e.detail}</p><small>{e.timestamp}</small></div>{i!==events.length-1&&<div className="eventLine"/>}</div>):<div className="empty">No events yet.</div>}</div>}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
