from __future__ import annotations

import pytest

from agentcontract.protocol.protocol import AgentContractProtocol


@pytest.fixture()
def protocol(tmp_path):
    return AgentContractProtocol(db_path=tmp_path / "agentcontract.db")


@pytest.fixture()
def registered(protocol):
    protocol.register_agent("agent-a", "worker", ["modify"], ["auth/"], 0.7)
    protocol.register_agent("agent-b", "worker", ["refactor"], ["checkout/"], 0.9)
    protocol.register_agent("agent-c", "worker", ["modify"], ["auth/tokens.py"], 0.8)
    return protocol
