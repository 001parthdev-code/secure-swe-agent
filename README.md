# Secure Goal-Directed Autonomous Software Engineering Agent

> An engineering-research project exploring autonomous software engineering under externally enforced security constraints.

## Overview

This project aims to build a goal-directed autonomous software-engineering agent capable of taking a repository-level software issue and iteratively working toward a verified solution.

The agent is expected to:

1. understand an assigned software issue,
2. inspect an unfamiliar repository,
3. gather relevant context,
4. form hypotheses about the problem,
5. construct and revise plans,
6. request tool actions,
7. modify code,
8. execute tests and development tools,
9. interpret external evidence,
10. recover from unsuccessful approaches, and
11. continue until sufficient verification evidence exists or a controlled termination condition is reached.

The project is intentionally divided into two components:

- **Engineering:** build the autonomous software-engineering agent and its security architecture.
- **Research:** use the instrumented system to empirically study goal-directed agent behavior under externally enforced capability constraints.

---

## Core Architecture

The system separates agent intelligence from execution authority.

```text
                 Repository + Issue
                        |
                        v
              +-------------------+
              |   Python Agent    |
              |    UNTRUSTED      |
              |                   |
              | Goal State        |
              | Agent Loop        |
              | Context           |
              | Hypotheses        |
              | Planning          |
              | Verification      |
              | Recovery          |
              +---------+---------+
                        |
                 CapabilityRequest
                        |
================== TRUST BOUNDARY ==================
                        |
                        v
              +-------------------+
              |   Rust Enforcer   |
              |      TRUSTED      |
              |                   |
              | Validate          |
              | Authorize         |
              | Constrain         |
              | Execute           |
              | Audit             |
              +---------+---------+
                        |
                        v
              +-------------------+
              |     Isolated      |
              |     Workspace     |
              +-------------------+
                        |
                    ToolResult
                        |
                        v
                  Python Agent
````

### Architectural Principle

> **The agent possesses intent; the enforcer possesses authority.**

The language model and Python agent runtime are treated as untrusted.

Agent-controlled security-sensitive operations must pass through the Rust enforcement layer before they can affect protected resources.

---

## Goal-Directed Agent Loop

The agent is not intended to be a simple repeated LLM call.

The planned control loop is approximately:

```text
GOAL
  |
  v
OBSERVE
  |
  v
HYPOTHESIZE
  |
  v
PLAN
  |
  v
REQUEST ACTION
  |
  v
ENFORCE
  |
  +---- DENY ----+
  |              |
  v              |
EXECUTE           |
  |              |
  +-------+------+
          |
          v
       OBSERVE
          |
          v
        VERIFY
          |
          v
     UPDATE STATE
          |
     +----+----+
     |         |
 unresolved  verified
     |         |
     v         v
   REPLAN   TERMINATE
```

Successful termination should depend on external verification evidence rather than solely on the model claiming that the task has been solved.

---

## Security Model

The Python agent is explicitly considered untrusted.

This includes:

* the language model,
* agent reasoning,
* agent-generated tool requests,
* repository content,
* issue content,
* source-code comments,
* repository documentation, and
* potentially hostile or compromised dependencies.

The Rust enforcement layer forms the trusted security boundary.

### Initial Security Invariant

> No security-sensitive operation requested by an untrusted agent component may affect a protected resource without authorization by the Rust enforcement layer.

The enforcement layer is expected to eventually mediate capabilities such as:

* filesystem access,
* process execution,
* command execution,
* environment access,
* network access,
* resource consumption,
* execution time,
* protected security state, and
* audit logging.

---

## Research Direction

The system will also serve as an instrumented experimental platform.

The initial research question is deliberately exploratory:

> How do goal-directed autonomous software-engineering agents behave when progress toward an assigned objective interacts with externally enforced capability constraints?

Initial areas of investigation include:

* behavior following capability denial,
* legitimate recovery after denied actions,
* strategy substitution,
* repeated prohibited requests,
* controlled security affordance discovery,
* capability composition,
* verification manipulation, and
* the relationship between agent-loop architecture and security behavior.

The project does **not** currently claim that these behaviors are novel or that any particular phenomenon will occur.

Exploratory observations will be compared against existing literature before specific hypotheses or research contributions are claimed.

---

## Experimental Philosophy

Security experiments will use isolated, controlled scenario fixtures.

For example, an experimental environment may intentionally contain a policy-prohibited shortcut that would make a software-engineering objective easier to accomplish.

The experiment can then observe whether the agent:

* ignores the shortcut,
* requests it,
* receives a denial and complies,
* finds a legitimate alternative,
* repeats the request,
* changes strategy, or
* discovers another route.

Experimental affordances are separate from the production security implementation.

---

## Repository Structure

```text
secure-swe-agent/
|
+-- agent/             # Python agent runtime (untrusted)
|
+-- enforcer/          # Rust security enforcement layer (trusted)
|
+-- workspace/         # Controlled repository workspace
|
+-- trajectories/      # Agent execution traces
|
+-- experiments/       # Controlled research scenarios
|
+-- docs/              # Architecture, research, threat model, etc.
|
+-- README.md
```

The structure will evolve as the system develops.

---

## Current Development Stage

**Status: Early POC**

The first engineering milestone is establishing the communication and trust boundary between the Python agent runtime and Rust enforcer.

Initial capability requests will include operations such as:

```text
ReadFile
WriteFile
RunCommand
```

The first security acceptance test is:

```text
Python requests:
    read_file("hello.txt")

Rust:
    ALLOW

Result:
    file contents returned
```

while:

```text
Python requests:
    read_file("../../outside.txt")

Rust:
    DENY

Result:
    protected file is never accessed
```

Once this boundary is operational, the model and goal-directed agent loop will be introduced incrementally.

---

## Planned Development

```text
Phase 0    Project specification + literature review

Phase 1    Python <-> Rust capability boundary

Phase 2    Minimal goal-directed agent loop

Phase 3    Repository exploration + modification

Phase 4    Verification + failure recovery

Phase 5    Security hardening + isolation

Phase 6    Engineering evaluation

Phase 7    Exploratory security experiments

Phase 8    Hypothesis-driven research, if warranted
```

---

## Project Status

This project is under active development.

The architecture, research questions, experimental methodology, and implementation are expected to evolve as engineering evidence and literature review expose new constraints and failure modes.



