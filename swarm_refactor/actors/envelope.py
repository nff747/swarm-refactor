"""Immutable typed envelope for Actor-to-Actor message passing."""

from typing import Any, Generic, TypeVar, Optional
import uuid
import time
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")

class Envelope(BaseModel, Generic[T]):
    """Message envelope guaranteeing actor isolation and correlation tracking."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: str
    recipient: str
    message_type: str
    payload: Any
    correlation_id: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)

    model_config = ConfigDict(frozen=True)
