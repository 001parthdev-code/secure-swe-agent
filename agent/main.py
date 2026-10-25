"""A2 repository-analysis CLI. Run: python agent/main.py --help"""
import argparse
import json
from pathlib import Path
from secure_swe_agent.agent import Agent
from secure_swe_agent.catalog import load_catalog, valid_path
from secure_swe_agent.enforcer import EnforcerClient
from secure_swe_agent.ollama import Ollama


def main():
    parser = argparse.ArgumentParser(description='Secure SWE Agent A2 (read-only repository analysis)')
    parser.add_argument('task')
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--enforcer', required=True, type=Path)
    parser.add_argument('--file', action='append', default=[], dest='files',
                        help='Operator-approved workspace-relative file (repeatable)')
    parser.add_argument('--manifest', type=Path,
                        help='Operator-curated JSON manifest: {"files":["src/main.rs"]}')
    parser.add_argument('--model', default='qwen3.5:4b')
    parser.add_argument('--steps', type=int, default=10)
    args = parser.parse_args()
    files = list(args.files)
    if args.manifest:
        files.extend(load_catalog(args.manifest))
    if not files or len(set(files)) > 200 or any(not valid_path(p) for p in files):
        parser.error('provide 1-200 valid approved relative paths via --file or --manifest')
    with EnforcerClient(args.enforcer, args.workspace) as enforcer:
        outcome = Agent(Ollama(model=args.model), enforcer, sorted(set(files)), args.steps).run(args.task)
    print(json.dumps(outcome, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
