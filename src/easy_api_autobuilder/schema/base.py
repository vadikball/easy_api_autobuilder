"""Pydantic custom base model."""
from typing import Any
from uuid import UUID

from pydantic import BaseModel as _BaseModel, ConfigDict


class BaseModel(_BaseModel):
    model_config = ConfigDict(from_attributes=True)

    def put_dump(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)


class IntegerIdSchema(BaseModel):
    id: int


class UUIDIdSchema(BaseModel):
    id: UUID
