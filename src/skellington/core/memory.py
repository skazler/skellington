"""
SQLite-backed agent memory.

Learning goal: Persistent state and memory for agents. Agents can remember:
- Past conversations
- Task history
- Learned facts (long-term memory)
- Working context (short-term memory)

Uses SQLAlchemy async for non-blocking DB operations.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import Column, DateTime, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from skellington.core.config import get_settings

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# SQLAlchemy models
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


class ConversationRecord(Base):
    """Stores conversation history for agents."""

    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    agent_name = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class MemoryRecord(Base):
    """Stores key-value memories for agents (long-term)."""

    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String, nullable=False, index=True)
    key = Column(String, nullable=False)
    value = Column(Text, nullable=False)  # JSON-encoded
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TaskRecord(Base):
    """Stores task history."""

    __tablename__ = "task_history"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, nullable=False)
    assigned_to = Column(String)
    result = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Memory manager
# ---------------------------------------------------------------------------


class AgentMemory:
    """
    Async SQLite memory store for agents.

    Usage:
        memory = AgentMemory()
        await memory.initialize()

        # Store a memory
        await memory.remember("zero", "last_repo_path", "/path/to/project")

        # Recall a memory
        path = await memory.recall("zero", "last_repo_path")
    """

    def __init__(self, db_path: Path | None = None) -> None:
        settings = get_settings()
        self._db_path = db_path or settings.memory_db_path
        self._engine = None
        self._session_factory = None

    async def initialize(self) -> None:
        """Create the database and tables if they don't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite+aiosqlite:///{self._db_path}"

        self._engine = create_async_engine(db_url, echo=False)
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info("memory initialized", db_path=str(self._db_path))

    def _require_session(self) -> async_sessionmaker:
        if self._session_factory is None:
            raise RuntimeError("Call AgentMemory.initialize() before using memory.")
        return self._session_factory

    async def remember(self, agent: str, key: str, value: Any) -> None:
        """Store or update a key-value memory for an agent."""
        factory = self._require_session()
        encoded = json.dumps(value)

        async with factory() as session:
            result = await session.execute(
                select(MemoryRecord).where(
                    MemoryRecord.agent_name == agent,
                    MemoryRecord.key == key,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.value = encoded
                existing.updated_at = datetime.utcnow()
            else:
                session.add(MemoryRecord(agent_name=agent, key=key, value=encoded))

            await session.commit()

    async def recall(self, agent: str, key: str) -> Any | None:
        """Retrieve a stored memory value, or None if not found."""
        factory = self._require_session()
        async with factory() as session:
            result = await session.execute(
                select(MemoryRecord).where(
                    MemoryRecord.agent_name == agent,
                    MemoryRecord.key == key,
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                return None
            return json.loads(record.value)

    async def save_message(self, agent: str, session_id: str, role: str, content: str) -> None:
        """Append a message to an agent's conversation history."""
        factory = self._require_session()
        async with factory() as session:
            session.add(
                ConversationRecord(
                    agent_name=agent,
                    session_id=session_id,
                    role=role,
                    content=content,
                )
            )
            await session.commit()

    async def get_conversation(
        self, agent: str, session_id: str, limit: int = 50
    ) -> list[dict[str, str]]:
        """Retrieve the last N messages for an agent's session."""
        factory = self._require_session()
        async with factory() as session:
            result = await session.execute(
                select(ConversationRecord)
                .where(
                    ConversationRecord.agent_name == agent,
                    ConversationRecord.session_id == session_id,
                )
                .order_by(ConversationRecord.created_at.desc())
                .limit(limit)
            )
            records = result.scalars().all()
            return [{"role": r.role, "content": r.content} for r in reversed(records)]
