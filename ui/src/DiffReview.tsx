import type { Change } from './contracts';

type DiffLine = { kind: 'removed' | 'added' | 'context'; content: string };

// A minimal, deterministic line diff for the mock UI. The production API must
// provide a server-reviewed patch; this component is display-only.
function lines(text: string): string[] { return text.split('\n'); }
function compare(before: string, after: string): DiffLine[] {
  const left = lines(before);
  const right = lines(after);
  let prefix = 0;
  while (prefix < left.length && prefix < right.length && left[prefix] === right[prefix]) prefix++;
  let suffix = 0;
  while (suffix < left.length - prefix && suffix < right.length - prefix &&
    left[left.length - suffix - 1] === right[right.length - suffix - 1]) suffix++;
  return [
    ...left.slice(0, prefix).map(content => ({kind:'context' as const, content})),
    ...left.slice(prefix, left.length - suffix).map(content => ({kind:'removed' as const, content})),
    ...right.slice(prefix, right.length - suffix).map(content => ({kind:'added' as const, content})),
    ...(suffix ? left.slice(left.length - suffix) : []).map(content => ({kind:'context' as const, content})),
  ];
}

export function DiffReview({change}: {change?: Change}) {
  if (!change) return <div className="empty diffEmpty">No proposed changes available.</div>;
  if (change.diff) return <div className="diff" role="region" aria-label={`Proposed diff for ${change.path}`}>
    {change.diff.split('\n').filter(Boolean).map((content,index)=>{
      const kind = content.startsWith('+')&&!content.startsWith('+++')?'added':content.startsWith('-')&&!content.startsWith('---')?'removed':'context';
      return <div key={index} className={`diffLine ${kind}`}><span aria-hidden="true">{kind==='added'?'+':kind==='removed'?'−':' '}</span><code>{content}</code></div>;
    })}
  </div>;
  return <div className="diff" role="region" aria-label={`Proposed diff for ${change.path}`}>
    {compare(change.before, change.after).map((line, index) =>
      <div key={index} className={`diffLine ${line.kind}`}>
        <span aria-hidden="true">{line.kind === 'removed' ? '−' : line.kind === 'added' ? '+' : ' '}</span>
        <code>{line.content || ' '}</code>
      </div>)}
  </div>;
}
