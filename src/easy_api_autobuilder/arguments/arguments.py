from pydantic import BaseModel

from easy_api_autobuilder.arguments.schema_factory import SchemaCreationArguments


class BuilderArguments(BaseModel):
    schema_creation_args: SchemaCreationArguments | None = None
