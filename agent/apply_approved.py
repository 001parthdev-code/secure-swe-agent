"""Explicit operator CLI for inspecting and applying an A3 proposal on Linux."""
import argparse
import json
from pathlib import Path
import sys

from secure_swe_agent.approval import ApprovalError, apply_approved, digest, load_proposal
from secure_swe_agent.enforcer import EnforcerClient


def main():
    p = argparse.ArgumentParser(description='Inspect or explicitly approve an A3 proposal')
    p.add_argument('--proposal', type=Path, required=True)
    p.add_argument('--workspace', type=Path)
    p.add_argument('--enforcer', type=Path)
    p.add_argument('--approve-sha256', help='Exact SHA256 printed by inspection')
    p.add_argument('--trusted-exclusive-workspace', action='store_true',
                   help='Operator asserts disposable, exclusive Linux workspace; NOT isolation proof')
    args = p.parse_args()
    try:
        raw = args.proposal.read_bytes()
        proposal = load_proposal(raw)
        fingerprint = digest(raw)
        if args.approve_sha256 is None:
            print(json.dumps({'status': 'review_required', 'proposal_sha256': fingerprint,
                              'changes': [{'path': c['path'], 'diff_untrusted': c.get('diff', ''),
                                           'new_content': c['new_content'],
                                           'base_sha256': c['base_sha256']}
                                          for c in proposal['changes']]}, indent=2))
            return 0
        if args.approve_sha256 != fingerprint:
            raise ApprovalError('proposal changed since review')
        if sys.platform != 'linux' or not args.trusted_exclusive_workspace:
            raise ApprovalError('application requires explicit trusted Linux workspace opt-in')
        if args.workspace is None or args.enforcer is None:
            raise ApprovalError('--workspace and --enforcer required for application')
        with EnforcerClient(args.enforcer, args.workspace, trusted_exclusive=True) as client:
            outcome = apply_approved(proposal, client, {c['path'] for c in proposal['changes']})
        print(json.dumps(outcome, indent=2))
        return 0 if outcome['status'] == 'applied' else 1
    except (ApprovalError, OSError, RuntimeError) as exc:
        print(json.dumps({'status': 'rejected', 'reason': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
