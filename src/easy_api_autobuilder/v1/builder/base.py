import copy
from typing import TYPE_CHECKING, Annotated, Optional

from fastapi import APIRouter, Depends
from fastapi.params import Depends as DependsClass
from sqlalchemy.ext.asyncio import AsyncSession

from easy_api_autobuilder.v1.arguments import BuilderArguments
from easy_api_autobuilder.v1.lib_types import DeclarativeMetaProtocol
from easy_api_autobuilder.v1.logger import get_default_logger
from easy_api_autobuilder.v1.repo import BaseRepo, SecondaryBaseRepo
from easy_api_autobuilder.v1.schema import SchemaCreationStrategy, SchemaFactory, SecondarySchemaCreationStrategy
from easy_api_autobuilder.v1.service import BaseService, SecondaryBaseService
from easy_api_autobuilder.v1.view import BaseView, SecondaryView, ServiceHandlersType

if TYPE_CHECKING:
    from loguru import Logger


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


def service_deps_factory(service: type[BaseService], repo_deps: DependsClass, logger: "Logger") -> DependsClass:
    def inner(repo: Annotated[BaseRepo | SecondaryBaseRepo, repo_deps]) -> BaseService:
        return service(repo, logger)

    return Depends(inner)


def secondary_service_deps_factory(service: type[SecondaryBaseService], repo_deps: DependsClass) -> DependsClass:
    def inner(repo: Annotated[BaseRepo | SecondaryBaseRepo, repo_deps]) -> SecondaryBaseService:
        return service(repo)

    return Depends(inner)


def repo_deps_factory(
    repo: type[BaseRepo | SecondaryBaseRepo], session_dependency: DependsClass, logger: "Logger"
) -> DependsClass:
    def inner(db_session: Annotated[AsyncSession, session_dependency]) -> BaseRepo:
        return repo(db_session, logger)

    return Depends(inner)


def repo_factory(model: type[DeclarativeMetaProtocol]) -> type[BaseRepo]:
    class AnonymousRepo(BaseRepo):
        _cls_model = model

    AnonymousRepo.__name__ = model.__name__.split("Model")[0]

    return AnonymousRepo


def secondary_repo_factory(model: type[DeclarativeMetaProtocol]) -> type[SecondaryBaseRepo]:
    class AnonymousRepo(SecondaryBaseRepo):
        _cls_model = model

    AnonymousRepo.__name__ = model.__name__.split("Model")[0]

    return AnonymousRepo


class DataMapperBuilder:
    def __init__(
        self,
        session_dependency: DependsClass | None = None,
        router: APIRouter | None = None,
        dependencies: dict[ServiceHandlersType, list[DependsClass]] | None = None,
        default_logger: Optional["Logger"] = None,
    ):
        if default_logger is None:
            default_logger = get_default_logger()

        self.default_logger = default_logger
        self.dependencies = dependencies or {}
        self.session_dependency = session_dependency
        self.router = router

    def build(
        self,
        model: type[DeclarativeMetaProtocol],
        prefix: str | None = None,
        session_dependency: DependsClass | None = None,
        repo: type[BaseRepo] | None = None,
        secondary: dict[str, tuple[type[DeclarativeMetaProtocol], type[BaseRepo] | None]] | None = None,
        arguments: BuilderArguments | None = None,
        router: APIRouter | None = None,
        repo_deps: DependsClass | None = None,
        dependencies: dict[ServiceHandlersType, list[DependsClass]] | None = None,
    ) -> BaseView:
        router = router or self.router or APIRouter(prefix=prefix or f"/{model.__tablename__}")
        self.session_dependency = session_dependency or self.session_dependency

        repo = repo or repo_factory(model)

        arguments = BuilderArguments() if arguments is None else arguments

        schema_factory = SchemaFactory(model, self.default_logger)
        schema_strategy = SchemaCreationStrategy(schema_factory, arguments.schema_creation_args)

        service = service_factory(schema_strategy, model.__name__.split("Model")[0])

        repo_deps = repo_deps or self.get_repo_dependency(repo)

        service_dependency = self.get_service_dependency(service, repo_deps)

        secondary_views = self.get_secondary_views(secondary)

        dependencies = copy.deepcopy(dependencies)
        if isinstance(dependencies, dict):
            for handler_name, deps in self.dependencies:
                try:
                    dependencies[handler_name].extend(deps)
                except KeyError:
                    dependencies[handler_name] = deps

        return BaseView(
            router, service, service_dependency, schema_strategy, self.default_logger, secondary_views, dependencies
        )

    def get_service_dependency(
        self,
        service: type[BaseService | SecondaryBaseService],
        repo_deps: DependsClass,
    ) -> DependsClass:
        if issubclass(service, BaseService):
            return service_deps_factory(service, repo_deps, self.default_logger)

        return secondary_service_deps_factory(service, repo_deps)

    def get_repo_dependency(self, repo: type[BaseRepo]) -> DependsClass:
        return repo_deps_factory(repo, self.session_dependency, self.default_logger)

    def get_secondary_views(
        self,
        secondary: dict[str, tuple[type[DeclarativeMetaProtocol], type[BaseRepo] | None]] | None = None,
    ) -> tuple[SecondaryView, ...] | None:
        if secondary is None:
            return

        s_views_container = []
        for secondary_prefix, (
            secondary_model,
            secondary_repo,
        ) in secondary.items():
            if secondary_repo is None:
                secondary_repo = Depends(secondary_repo_factory(secondary_model))

            secondary_schema_factory = SchemaFactory(secondary_model, self.default_logger)
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
