# AgentContract

AgentContract is an intent-first coordination protocol for multi-agent work on shared projects. Agents publish what they plan to do before acting, subscribe to relevant intents, negotiate conflicts, witness completed work, and update trust scores from observed compliance.

## Install

```bash
pip install -e .
```

## Quick Start

```bash
agentcontract init
agentcontract register felix-cto --type architect --scope architecture --scope auth/ --capability refactor --trust 0.9
agentcontract propose --agent felix-cto --type refactor --target auth/ --description "Refactor auth module"
agentcontract intents
agentcontract demo
```

By default the CLI stores data in `.agentcontract/agentcontract.db`. Set `AGENTCONTRACT_DB=/path/to.db` to use a different database.

## API

```bash
agentcontract serve --port 8000
```

Endpoints include:

- `POST /agents`
- `POST /intents`
- `GET /intents`
- `GET /conflicts`
- `POST /negotiate/{conflict_id}`
- `POST /witness/{intent_id}`
- `GET /agents/{id}/trust`
- `GET /contracts`
- `GET /health`

## Protocol

1. `PROPOSE`: an agent declares intent.
2. `CHECK`: active intents are checked for overlap and dependency clashes.
3. `APPROVE`: non-conflicting intents can proceed.
4. `NEGOTIATE`: conflicting agents exchange offers or accept a suggested compromise.
5. `ARBITRATE`: deterministic rules select a resolution when negotiation stalls.
6. `WITNESS`: actions are verified against declared intent.
7. `RECORD`: compliance updates the transparent trust score.
