from pydantic import BaseModel, Field

default_excluded_fields = {"id", "created_at", "updated_at"}


class BaseCreationArguments(BaseModel):
    defaults: dict | None = None
    excluded: set | None = None
    nested: bool = True
    name_postfix: str | None = None
    put: bool = False
    included: set | None = None


class ListArguments(BaseCreationArguments):
    nested: bool = False
    name_postfix: str = "List"


class DetailArguments(BaseCreationArguments):
    name_postfix: str = "Detail"


class PostArguments(BaseCreationArguments):
    excluded: set = default_excluded_fields
    nested: bool = False
    name_postfix: str = "InCreate"


class PutArguments(BaseCreationArguments):
    excluded: set = default_excluded_fields
    nested: bool = False
    name_postfix: str = "InUpdate"
    put: bool = True


class SchemaCreationArguments(BaseModel):
    list_args: ListArguments = Field(default_factory=ListArguments)
    detail_args: DetailArguments = Field(default_factory=DetailArguments)
    post_args: PostArguments = Field(default_factory=PostArguments)
    put_args: PutArguments = Field(default_factory=PutArguments)
