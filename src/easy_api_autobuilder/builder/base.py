from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.params import Depends as DependsClass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeMeta

from easy_api_autobuilder.arguments import BuilderArguments
from easy_api_autobuilder.repo import BaseRepo, SecondaryBaseRepo
from easy_api_autobuilder.schema import SchemaCreationStrategy, SchemaFactory, SecondarySchemaCreationStrategy
from easy_api_autobuilder.service import BaseService, SecondaryBaseService
from easy_api_autobuilder.view import BaseView, SecondaryView


def service_factory(schema_strategy: SchemaCreationStrategy, class_name: str | None = None) -> type[BaseService]:
    class AnonymousService(BaseService):
        _output_list = schema_strategy.list.response
        _inner_data_type = schema_strategy.list.inner_response_type
        _output_detail = schema_strategy.detail.response
        _input_create = schema_strategy.post.request.body
        _create_response = schema_strategy.post.response
        _input_update = schema_strategy.put.request.body

    if class_name is not None:
        AnonymousService.__name__ = class_name

    return AnonymousService


def secondary_service_factory(
    schema_strategy: SecondarySchemaCreationStrategy, class_name: str | None = None
) -> type[SecondaryBaseService]:
    class AnonymousSecondaryService(SecondaryBaseService):
        _output_list = schema_strategy.list.response
        _input_create = schema_strategy.post.request.body

    if class_name is not None:
        AnonymousSecondaryService.__name__ = class_name

    return AnonymousSecondaryService


def service_deps_factory(service: type[BaseService | SecondaryBaseService], repo_deps: Depends) -> DependsClass:
    def inner(repo: Annotated[BaseRepo | SecondaryBaseRepo, repo_deps]) -> BaseService:
        return service(repo)

    return Depends(inner)


def repo_deps_factory(repo: type[BaseRepo | SecondaryBaseRepo], session_dependency: DependsClass) -> DependsClass:
    def inner(db_session: Annotated[AsyncSession, session_dependency]) -> BaseRepo:
        return repo(db_session)

    return Depends(inner)


def repo_factory(model: DeclarativeMeta) -> type[BaseRepo]:
    class AnonymousRepo(BaseRepo):
        _cls_model = model

    AnonymousRepo.__name__ = model.__name__.split("Model")[0]

    return AnonymousRepo


def secondary_repo_factory(model: DeclarativeMeta) -> type[SecondaryBaseRepo]:
    class AnonymousRepo(SecondaryBaseRepo):
        _cls_model = model

    AnonymousRepo.__name__ = model.__name__.split("Model")[0]

    return AnonymousRepo


class DataMapperBuilder:
    def __init__(
        self,
        prefix: str,
        model: DeclarativeMeta,
        session_dependency: DependsClass,
        repo: type[BaseRepo] | None = None,
        secondary: dict[str, tuple[DeclarativeMeta, type[BaseRepo] | None]] | None = None,
        arguments: BuilderArguments | None = None,
    ):
        self.prefix = prefix

        self.session_dependency = session_dependency
        self.model = model
        self.repo = repo
        self.secondary = secondary
        self.arguments = BuilderArguments() if arguments is None else arguments

    def build(self) -> BaseView:
        router = APIRouter(prefix=self.prefix)

        if self.repo is None:
            self.repo = repo_factory(self.model)

        schema_factory = SchemaFactory(self.model)
        schema_strategy = SchemaCreationStrategy(schema_factory, self.arguments.schema_creation_args)

        service = service_factory(schema_strategy, self.model.__name__.split("Model")[0])
        service_dependency = self.get_service_dependency(service, self.repo)

        secondary_views = self.get_secondary_views()

        return BaseView(router, service, service_dependency, schema_strategy, secondary_views)

    def get_service_dependency(
        self,
        service: type[BaseService | SecondaryBaseService],
        repo: type[BaseRepo | SecondaryBaseRepo],
    ) -> DependsClass:
        repo_deps = repo_deps_factory(repo, self.session_dependency)
        return service_deps_factory(service, repo_deps)

    def get_secondary_views(self) -> tuple[SecondaryView, ...] | None:
        if self.secondary is None:
            return

        s_views_container = []
        for secondary_prefix, (
            secondary_model,
            secondary_repo,
        ) in self.secondary.items():
            if secondary_repo is None:
                secondary_repo = secondary_repo_factory(secondary_model)

            secondary_schema_factory = SchemaFactory(secondary_model)
            secondary_schema_strategy = SecondarySchemaCreationStrategy(secondary_schema_factory)

            secondary_service = secondary_service_factory(
                secondary_schema_strategy, secondary_model.__name__.split("Model")[0]
            )

            secondary_service_deps = self.get_service_dependency(secondary_service, secondary_repo)

            s_views_container.append(
                SecondaryView(
                    route=secondary_prefix,
                    schemas=secondary_schema_strategy,
                    service=secondary_service,
                    service_deps=secondary_service_deps,
                )
            )

        return tuple(s_views_container)
