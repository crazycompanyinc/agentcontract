"""HTTP routes for AgentContract."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agentcontract.core.db import AgentContractDB
from agentcontract.protocol.protocol import AgentContractProtocol

router = APIRouter()


class AgentRequest(BaseModel):
    agent_id: str
    agent_type: str = "general"
    capabilities: list[str] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=list)
    trust_score: float = 0.5


class IntentRequest(BaseModel):
    agent_id: str
    intent_type: str
    target: str
    description: str
    impact_scope: list[str] = Field(default_factory=list)
    estimated_duration: str | None = None
    dependencies: list[str] = Field(default_factory=list)


class NegotiationRequest(BaseModel):
    agent_id: str
    offer_text: str


class WitnessRequest(BaseModel):
    actual_action: str
    compliance_score: float | None = None


def protocol() -> AgentContractProtocol:
    return AgentContractProtocol(db=AgentContractDB())


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/agents")
async def register_agent(payload: AgentRequest) -> dict[str, Any]:
    return protocol().register_agent(**payload.model_dump()).to_dict()


@router.get("/agents")
async def list_agents() -> list[dict[str, Any]]:
    return [agent.to_dict() for agent in protocol().db.list_agents()]


@router.get("/agents/{agent_id}/trust")
async def trust(agent_id: str) -> dict[str, Any]:
    agent = protocol().db.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return {"agent_id": agent.agent_id, "trust_score": agent.trust_score}


@router.post("/intents")
async def create_intent(payload: IntentRequest) -> dict[str, Any]:
    try:
        result = protocol().propose_intent(**payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "state": result.state,
        "message": result.message,
        "intent": result.intent.to_dict(),
        "conflicts": [conflict.to_dict() for conflict in result.conflicts],
    }


@router.get("/intents")
async def list_intents() -> list[dict[str, Any]]:
    return [intent.to_dict() for intent in protocol().db.list_intents()]


@router.get("/conflicts")
async def list_conflicts() -> list[dict[str, Any]]:
    return [conflict.to_dict() for conflict in protocol().db.list_conflicts()]


@router.post("/negotiate/{conflict_id}")
async def negotiate(conflict_id: str, payload: NegotiationRequest) -> dict[str, Any]:
    try:
        return protocol().negotiate(conflict_id, payload.agent_id, payload.offer_text)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/witness/{intent_id}")
async def witness(intent_id: str, payload: WitnessRequest) -> dict[str, Any]:
    try:
        return protocol().witness(intent_id, payload.actual_action, payload.compliance_score).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/contracts")
async def list_contracts() -> list[dict[str, Any]]:
    return [contract.to_dict() for contract in protocol().db.list_contracts()]
