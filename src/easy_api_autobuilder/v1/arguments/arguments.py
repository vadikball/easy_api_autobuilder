from pydantic import BaseModel

from .schema_factory import SchemaCreationArguments


class BuilderArguments(BaseModel):
    schema_creation_args: SchemaCreationArguments | None = None
