import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, AlertTriangle, ArrowUpRight, Check, CheckCircle2, ChevronRight, Circle, ClipboardCheck, Code2, FileCode2, FolderGit2, GitBranch, GitCommitHorizontal, GitPullRequest, LayoutDashboard, LockKeyhole, Play, RefreshCcw, RotateCcw, ShieldCheck, TerminalSquare, X, XCircle } from 'lucide-react';
import { DiffReview } from './DiffReview';
import type { Task, TaskStatus, WorkflowApi } from './contracts';
import { liveApi } from './liveApi';
import './styles.css';

const api: WorkflowApi = liveApi;
type Section = 'workspace' | 'activity' | 'review';
type ReviewTab = 'diff' | 'tests';
type Decision = 'change' | 'commit' | 'publish' | 'reject';
const statuses: Record<TaskStatus,string> = {idle:'Idle',analyzing:'Analyzing',awaiting_change_approval:'Change review',applying:'Applying change',verifying:'Verifying',awaiting_commit_approval:'Commit review',reviewing_commit:'Preparing commit review',committing:'Committing',committed:'Committed',awaiting_publish_approval:'Publish review',reviewing_publish:'Preparing publication review',publishing:'Publishing',published:'Published',rejected:'Rejected',failed:'Failed',needs_reconciliation:'Needs reconciliation'};
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
  if (status==='awaiting_commit_approval'||status==='reviewing_commit'||status==='committing'||status==='committed') return 3;
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
  useEffect(()=>{let stopped=false;const refresh=()=>{void api.getTask().then(next=>{if(!stopped)setTask(next)}).catch(e=>{if(!stopped)setError(String(e))})};refresh();const interval=setInterval(refresh,2500);return ()=>{stopped=true;clearInterval(interval)}},[]);
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
    const messages:Record<Decision,string>={change:'Change approved.',commit:'Commit approved.',publish:'Publication approved.',reject:'Change rejected.'};
    void run(action[decision],messages[decision]);
  }
  const reviewTitle=decision==='change'?'Approve proposed code change?':decision==='commit'?'Approve Git commit?':decision==='publish'?'Approve GitHub publication?':'Reject proposed change?';
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
      <div className="environment"><span className="dot"/> Live local analysis</div>
      <div className="sideBottom"><LockKeyhole size={17}/><span>Local-only API preview<br/><small>Enforcer-mediated changes</small></span></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="crumb">Workspace <ChevronRight size={13}/> {section==='workspace'?'Overview':section==='activity'?'Task activity':'Review & publish'}</div><div className="topright"><span className="mode">LIVE APPROVAL</span><span className="avatar">UI</span></div></header>
      <div className="content">
        <div className="eyebrow">SECURE SOFTWARE ENGINEERING <span className="eyebrowLine"/></div>
        <div className="headline"><div><h1>{section==='workspace'?'Agent workspace':section==='activity'?'Execution activity':'Review center'}</h1><p>{section==='workspace'?'Run Qwen analysis and review a real proposal.':section==='activity'?'A timeline of actual local agent operations.':'Review changes, verification evidence, and publication checkpoints.'}</p></div><button className="outline" disabled={busy} onClick={()=>void run(()=>api.getTask(),'Task refreshed.')}><RefreshCcw size={15}/> Refresh</button></div>
        <div className="noticeBanner"><AlertTriangle size={17}/><span><strong>Controlled live mode.</strong> Qwen and the Rust Enforcer generate real proposals. Exact-change application is enabled for the trusted Linux calculator fixture. Git commits and publication require separate explicit reviews.</span></div>
        <div className="stats">
          <div className="stat"><span>MODEL</span><strong>Qwen 3.5 · 4B</strong><small>Local Ollama inference</small></div>
          <div className="stat"><span>ENFORCEMENT</span><strong><ShieldCheck size={18}/> Rust Enforcer</strong><small>Linux approval boundary</small></div>
          <div className="stat"><span>WORKFLOW</span><strong>Supervised</strong><small>Change approval connected</small></div>
        </div>
        <section className="panel journeyPanel" aria-label="Workflow stages"><div className="journeyHeader"><span className="sectionIndex">WORKFLOW OVERVIEW</span><span className="taskId">{task?.id??'Loading task...'}</span></div><div className="journey">{steps.map((s,i)=>{const Icon=s.icon;const done=!!task&&(i<current||task.status==='published');const active=!!task&&i===current&&task.status!=='published';return <div className={'journeyStep '+(done?'done ':active?'active ':'')} key={s.label}><div className="journeyIcon">{done?<Check size={16}/>:<Icon size={16}/>}</div><div><strong>{s.label}</strong><small>{s.detail}</small></div></div>})}</div></section>
        {section==='workspace'&&<section className="panel taskPanel"><div className="panelHead"><div><span className="sectionIndex">01 / TASK</span><h2>What should the agent do?</h2></div><span className="mutedPill"><FolderGit2 size={14}/> calculator-demo · fixed fixture</span></div><label className="inputLabel" htmlFor="task-description">Task description</label><textarea id="task-description" value={draft} maxLength={1200} onChange={e=>setDraft(e.target.value)} placeholder="Describe the calculator subtraction task..."/><div className="taskFoot"><span><LockKeyhole size={14}/> Trusted calculator fixture · supervised</span><button className="primaryBtn" disabled={busy||!draft.trim()} onClick={()=>void run(()=>api.startTask(draft),'Live analysis started.')}><Play size={15}/> Run live analysis</button></div></section>}
        <div className="columns"><div className="primary">
          {(section!=='activity')&&<section className="panel changesPanel"><div className="panelHead"><div><span className="sectionIndex">02 / REVIEW</span><h2>Code & verification</h2></div><div className="tabs" role="tablist" aria-label="Review content"><button role="tab" aria-selected={tab==='diff'} className={tab==='diff'?'active':''} onClick={()=>setTab('diff')}>Code diff</button><button role="tab" aria-selected={tab==='tests'} className={tab==='tests'?'active':''} onClick={()=>setTab('tests')}>Tests</button></div></div>
            {tab==='diff'?<><div className="fileBar"><FileCode2 size={17}/><span>{task?.changes[0]?.path??'No file selected'}</span><span className="fileCount">{task?.changes.length??0} file</span></div><DiffReview change={task?.changes[0]}/><p className="explanation">{task?.changes[0]?.explanation??'No change proposal available.'}</p></>:<div className="testBox">{task?.tests?<><div className="passed"><CheckCircle2 size={18}/>{task.tests.passed} passed · {task.tests.failed} failed</div><pre>{task.tests.output}</pre></>:<div className="empty"><TerminalSquare size={20}/> Live verification will appear when the approval API is connected.</div>}</div>}
            {status==='awaiting_change_approval'&&<div className="reviewActions"><button className="outline danger" disabled={busy} onClick={()=>setDecision('reject')}><XCircle size={15}/> Reject</button><button className="primaryBtn" disabled={busy} onClick={()=>setDecision('change')}><Check size={16}/> Review approval</button></div>}
            {status==='awaiting_commit_approval'&&<div className="reviewActions"><span className="inlineSuccess"><CheckCircle2 size={16}/> Tests passed</span><button className="primaryBtn" disabled={busy} onClick={()=>task?.commitReview?setDecision('commit'):void run(()=>api.reviewCommit(task!.id),'Staged diff ready for review.')}>{task?.commitReview?'Approve reviewed commit':'Prepare commit review'}</button></div>}
            {(status==='awaiting_publish_approval'||status==='committed')&&<div className="reviewActions"><span className="quiet">Target: demo repository · main</span><button className="primaryBtn" disabled={busy} onClick={()=>task?.publishReview?setDecision('publish'):void run(()=>api.reviewPublish(task!.id),'GitHub plan ready for review.')}>{task?.publishReview?'Approve reviewed publication':'Prepare publication review'}</button></div>}
            {status==='published'&&<div className="reviewActions"><span className="inlineSuccess"><CheckCircle2 size={16}/> Publication complete</span><a className="prLink" href={task?.prUrl??'#'} target="_blank" rel="noreferrer">Open PR <ArrowUpRight size={15}/></a></div>}
            {status==='rejected'&&<div className="reviewActions"><span className="quiet">Proposal rejected · No files changed</span><button className="outline" onClick={()=>void run(()=>api.startTask(draft),'Simulation restarted.')} disabled={busy}><RotateCcw size={15}/> Restart</button></div>}
          </section>}
          {section==='activity'&&<section className="panel activityFull"><div className="panelHead"><div><span className="sectionIndex">FULL EVENT LOG</span><h2>Workflow timeline</h2></div><Activity size={18}/></div><Timeline task={task}/></section>}
          {section==='review'&&<section className="panel publishPanel"><div className="panelHead"><div><span className="sectionIndex">03 / PUBLICATION</span><h2>GitHub destination</h2></div><GitPullRequest size={18}/></div><div className="publishDetails"><div><span>Repository</span><strong>001parthdev-code/secure-swe-agent-demo</strong></div><div><span>Base branch</span><strong>main</strong></div><div><span>Task branch</span><strong>{task?.branch??'—'}</strong></div><div><span>Publication</span><strong>{status==='published'?'Published':'Not published'}</strong></div></div></section>}
        </div><div className="secondary"><section className="panel statusPanel"><div className="panelHead"><div><span className="sectionIndex">TASK STATUS</span><h2>Current state</h2></div><span className="liveDot"/></div><div className="taskId">{task?.id??'Loading...'}</div><div className="statusBadge"><span className="dot"/>{task?statuses[task.status]:'Loading'}</div><div className="divider"/><div className="metadata"><span><GitBranch size={15}/> Branch</span><strong>{task?.branch??'—'}</strong></div><div className="metadata"><span><Code2 size={15}/> Repository</span><strong>{task?.repository??'—'}</strong></div><div className="metadata"><span><LockKeyhole size={15}/> Checkpoint</span><strong>{actionable?'Human approval':'None pending'}</strong></div></section>{section!=='activity'&&<section className="panel activityPanel"><div className="panelHead"><div><span className="sectionIndex">EVENT LOG</span><h2>Recent activity</h2></div><button className="textButton" onClick={()=>setSection('activity')}>View all <ArrowUpRight size={14}/></button></div><Timeline task={task} limit={4}/></section>}<section className="panel helperPanel"><span className="sectionIndex">SECURITY BOUNDARY</span><div className="helperTitle"><ShieldCheck size={19}/> Approvals stay server-side</div><p>The backend revalidates the exact proposal and original file before invoking the Linux Enforcer. Commit and publication approvals are independently validated by the backend.</p></section></div></div>
        {error&&<div className="error" role="alert"><AlertTriangle size={17}/>{error}<button aria-label="Dismiss error" onClick={()=>setError('')}><X size={15}/></button></div>}
        {notice&&<div className="toast" role="status"><CheckCircle2 size={16}/>{notice}<button aria-label="Dismiss notice" onClick={()=>setNotice('')}><X size={14}/></button></div>}
        <footer>SECURE SWE AGENT <span>·</span> LOCAL LIVE APPROVAL <span>·</span> SUPERVISED GIT & PUBLICATION</footer>
      </div>
    </main>
    {decision&&task&&<div className="modalBackdrop" onMouseDown={e=>{if(e.target===e.currentTarget&&!busy)setDecision(null)}}><div className="modal" role="dialog" aria-modal="true" aria-labelledby="decision-title"><div className="modalTop"><div className="modalIcon"><LockKeyhole size={20}/></div><button className="iconButton" aria-label="Close approval dialog" disabled={busy} onClick={()=>setDecision(null)}><X size={18}/></button></div><h2 id="decision-title">{reviewTitle}</h2><p>{decision==='change'?'Approve this exact proposal for Linux Enforcer application?':decision==='reject'?'Reject this proposal without modifying files?':'Confirm only after reviewing the exact staged diff or GitHub destination below.'}</p>{decision==='commit'&&task.commitReview&&<pre style={{maxHeight:220,overflow:'auto',whiteSpace:'pre-wrap'}}>{task.commitReview.diff}</pre>}
          {decision==='publish'&&task.publishReview&&<div className="approvalFacts"><div><span>Destination</span><strong>{task.publishReview.github_repo}</strong></div><div><span>Base</span><strong>{task.publishReview.base}</strong></div><div><span>Commit</span><strong>{task.publishReview.head}</strong></div><div><span>Title</span><strong>{task.publishReview.title}</strong></div><div><span>Description</span><strong>{task.publishReview.body}</strong></div></div>}
          <div className="approvalFacts"><div><span>Task</span><strong>{task.id}</strong></div><div><span>Revision</span><strong>{task.revision}</strong></div><div><span>Repository</span><strong>{task.repository}</strong></div><div><span>Operation</span><strong>{decision}</strong></div></div><div className="modalActions"><button className="outline" disabled={busy} onClick={()=>setDecision(null)}>Cancel</button><button className={'primaryBtn '+(decision==='reject'?'rejectBtn':'')} disabled={busy} onClick={decide}>{busy?'Working...':decision==='reject'?'Reject':'Confirm approval'}</button></div></div></div>}
  </div>;
}
function Timeline({task,limit}:{task:Task|null;limit?:number}){const events=limit?task?.events.slice(-limit):task?.events;return <div className="timeline">{events?.length?events.map((e,i)=><div className="event" key={e.id}><div className={'eventIcon '+e.kind}>{e.kind==='error'?<XCircle size={14}/>:e.kind==='pending'?<Circle size={13}/>:<Check size={14}/>}</div><div><strong>{e.title}</strong><p>{e.detail}</p><small>{e.timestamp}</small></div>{i!==events.length-1&&<div className="eventLine"/>}</div>):<div className="empty">No events yet.</div>}</div>}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
