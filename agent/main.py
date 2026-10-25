"""A1 read-only CLI. Run: python agent/main.py --help"""
import argparse
import json
from pathlib import Path
from secure_swe_agent.agent import Agent
from secure_swe_agent.enforcer import EnforcerClient
from secure_swe_agent.ollama import Ollama


def main():
    parser = argparse.ArgumentParser(description='Secure SWE Agent A1 (read-only)')
    parser.add_argument('task')
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--enforcer', required=True, type=Path, help='Path to enforcer-cli binary')
    parser.add_argument('--file', action='append', required=True, dest='files',
                        help='Approved relative file path; repeat for multiple files')
    parser.add_argument('--model', default='qwen3.5:4b')
    parser.add_argument('--steps', type=int, default=6)
    args = parser.parse_args()
    with EnforcerClient(args.enforcer, args.workspace) as enforcer:
        outcome = Agent(Ollama(model=args.model), enforcer, args.files, args.steps).run(args.task)
    print(json.dumps(outcome, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
