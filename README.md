# AgentContract

AgentContract is an intent-first coordination protocol for multi-agent work on shared projects. Agents publish what they plan to do before acting, subscribe to relevant intents, negotiate conflicts, witness completed work, and update trust scores from observed compliance.

Version 2.0 adds production-grade coordination services around the original protocol: a SQLite-backed persistent message queue, capability discovery, intent and contract templates, dependency scheduling, conflict prediction, teams, full audit trails, health monitoring, integration webhooks, advanced multi-round negotiation, and a multi-dimensional reputation market.

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

## v2.0 Services

The main `AgentContractProtocol` object exposes the v2 services directly:

- `protocol.queue`: durable async messages with leases, retries, acknowledgements, and dead-letter queues.
- `protocol.discovery`: advertise capabilities and answer "who can do X?" queries.
- `protocol.intent_templates`: validated templates for deploy, refactor, hotfix, feature-add, and bug-fix intents.
- `protocol.dependencies`: dependency graph blocking, runnable intent calculation, cycle detection, and auto-scheduling.
- `protocol.conflict_predictor`: historical conflict probability estimates by agent pair and resource.
- `protocol.teams`: team membership, shared scope, shared intents, and team contracts.
- `protocol.contract_templates`: pair-programming, code-review, and deploy-pipeline contract templates.
- `protocol.audit`: timestamped audit events with details and evidence.
- `protocol.health`: responsiveness, completion rate, compliance rate, and unhealthy-agent flags.
- `protocol.webhooks`: event subscriptions and signed async delivery for external integrations.
- `protocol.advanced_negotiation`: structured counter-offers, compromise suggestions, round limits, and timeout escalation.
- `protocol.reputation`: quality, speed, communication, and reliability ratings between agents.

Use `protocol.v2_ledger()` for an expanded ledger that includes the v2 audit, queue, discovery, teams, and reputation sections. The original `protocol.ledger()` keeps its v1 shape for compatibility.
