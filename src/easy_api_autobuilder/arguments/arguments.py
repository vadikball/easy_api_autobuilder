from pydantic import BaseModel

from arguments.schema_factory import SchemaCreationArguments


class BuilderArguments(BaseModel):
    schema_creation_args: SchemaCreationArguments | None = None
