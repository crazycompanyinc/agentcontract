"""Conflict detection and resolution."""

from agentcontract.conflict.detector import ConflictDetector
from agentcontract.conflict.negotiation import NegotiationEngine
from agentcontract.conflict.resolution import ResolutionProtocol

__all__ = ["ConflictDetector", "NegotiationEngine", "ResolutionProtocol"]
