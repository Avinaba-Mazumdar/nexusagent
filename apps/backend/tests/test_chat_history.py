from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
from app.db.models import User
from app.db.neon import neon_db
from app.main import app


@pytest.mark.asyncio
async def test_chat_history_unauthenticated_forbidden():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/chat/history")
        assert response.status_code == 401


@pytest.mark.db
@pytest.mark.asyncio
async def test_chat_history_guest_forbidden():
    transport = ASGITransport(app=app)
    guest_id = uuid4()
    guest_user = User(
        id=guest_id,
        name="Guest Architect",
        is_guest=True,
    )
    if neon_db.pool:
        await neon_db.create_user(guest_user)

    token, _ = create_access_token({"sub": str(guest_id), "role": "guest", "is_guest": True})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/chat/history", headers=headers)
        assert response.status_code == 403
        data = response.json()
        assert "exclusively available for authenticated Google accounts" in data["detail"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_chat_history_google_user_crud():
    transport = ASGITransport(app=app)
    user_id = uuid4()
    google_user = User(
        id=user_id,
        email=f"developer-{uuid4().hex[:8]}@nexusagent.test",
        name="Google Dev",
        is_guest=False,
    )
    if neon_db.pool:
        await neon_db.create_user(google_user)

    token, _ = create_access_token({"sub": str(user_id), "role": "user", "is_guest": False})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. List history initially empty
        res = await client.get("/api/chat/history", headers=headers)
        assert res.status_code == 200
        assert "conversations" in res.json()

        # 2. Conversations are created by the agent stream; seed one directly
        created = await neon_db.create_conversation(user_id, title="Raft Consensus Analysis")
        conv_id = str(created["id"])
        assert created["title"] == "Raft Consensus Analysis"

        # 3. Retrieve conversation detail
        res_detail = await client.get(f"/api/chat/history/{conv_id}", headers=headers)
        assert res_detail.status_code == 200
        assert res_detail.json()["conversation"]["id"] == conv_id

        # 4. The list includes it, with timestamps
        res_list = await client.get("/api/chat/history", headers=headers)
        assert res_list.status_code == 200
        listed = next(c for c in res_list.json()["conversations"] if c["id"] == conv_id)
        assert listed["updatedAt"]

        # 5. Delete conversation
        res_del = await client.delete(f"/api/chat/history/{conv_id}", headers=headers)
        assert res_del.status_code == 200
        assert res_del.json()["success"] is True


@pytest.mark.db
@pytest.mark.asyncio
async def test_follow_up_turn_keeps_first_title():
    """LOG-02: a follow-up turn must not rename the conversation to the latest question."""
    from app.agent.state import AgentState
    from app.services.conversations import persist_turn

    user_id = uuid4()
    await neon_db.create_user(
        User(
            id=user_id,
            email=f"title-{uuid4().hex[:8]}@nexusagent.test",
            name="Title Tester",
            is_guest=False,
        )
    )
    session_id = str(uuid4())

    for query in ("How does Raft elect a leader?", "And what about log compaction?"):
        state = AgentState(query=query, session_id=session_id, response="answer")
        assert await persist_turn(user_id, session_id, query, state) == session_id

    conv, messages = await neon_db.get_conversation_with_messages(user_id, UUID(session_id))
    assert conv is not None
    assert conv["title"] == "How does Raft elect a leader?"
    assert len(messages) == 4
