"""BaseView definition."""
from dataclasses import dataclass
from typing import Annotated, Callable, Literal

from fastapi import APIRouter, Body, Depends, Response
from fastapi.params import Depends as DependsClass

from easy_api_autobuilder.schema import BaseSchemaCreationStrategy, StrategyReturn
from easy_api_autobuilder.service import BaseService, SecondaryBaseService

get_handlers = frozenset(
    (
        "list",
        "detail",
    )
)
not_pk_handler = frozenset(
    (
        "list",
        "post",
    )
)


def exclude_parameter() -> None:
    return None


ExcludeFieldAnnotation = Annotated[None, Depends(exclude_parameter)]

secondary_route_sample = "{0}/{1}{2}"


@dataclass
class SecondaryView:
    route: str
    service: type[SecondaryBaseService]
    service_deps: DependsClass
    schemas: BaseSchemaCreationStrategy
    secondary_handlers: frozenset = frozenset(
        (
            "list",
            "delete",
            "post",
        )
    )

    def make_route(self, handler_name: str) -> str:
        if handler_name == "post":
            return secondary_route_sample.format("", self.route, "")

        if handler_name == "list":
            return secondary_route_sample.format("/{model_pk}", self.route, "")

        return secondary_route_sample.format("/{model_pk}", self.route, "/{secondary_model_pk}")


class BaseView:
    handlers: frozenset = frozenset(
        (
            "list",
            "detail",
            "delete",
            "post",
            "put",
        )
    )

    def __init__(
        self,
        router: APIRouter,
        main_service: type[BaseService],
        main_service_deps: DependsClass,
        main_schemas: BaseSchemaCreationStrategy,
        secondary_views: tuple[SecondaryView, ...] | None = None,
    ):
        self.router = router
        self._main_service = main_service
        self._main_service_deps = main_service_deps
        self._main_schemas = main_schemas

        self._secondary_views = secondary_views if secondary_views is not None else tuple()

        self._init()

    def _init(self) -> None:
        for handler_name in self.handlers:
            self._create_main_handler(handler_name)

        for secondary_view in self._secondary_views:
            for handler_name in secondary_view.secondary_handlers:
                self._create_secondary_handler(handler_name, secondary_view)

    def _response_code(self, method: str) -> int:
        if method == "DELETE":
            return 204
        if method == "POST":
            return 201

        return 200

    def _add_api_route(
        self,
        service_handler: str,
        annotations: StrategyReturn,
        route: str,
        service_deps: DependsClass,
        service: type[BaseService | SecondaryBaseService],
    ) -> None:
        method = service_handler.upper() if service_handler not in get_handlers else "GET"
        response_code = self._response_code(method)

        self.router.add_api_route(
            route,
            self._create_handler(
                service_handler,
                annotations,
                service_deps,
                service,
                response_code,
            ),
            methods={method},
            status_code=response_code,
        )

    def _create_main_handler(self, service_handler: Literal["list", "detail", "post", "put", "delete"]) -> None:
        route = "" if service_handler in not_pk_handler else "/{model_pk}"
        annotations: StrategyReturn = getattr(self._main_schemas, service_handler)

        self._add_api_route(
            service_handler,
            annotations,
            route,
            self._main_service_deps,
            self._main_service,
        )

    def _create_secondary_handler(
        self,
        service_handler: Literal["list", "detail", "post", "put", "delete"],
        secondary_view: SecondaryView,
    ) -> None:
        route = secondary_view.make_route(service_handler)
        annotations: StrategyReturn = getattr(secondary_view.schemas, service_handler)

        self._add_api_route(
            service_handler,
            annotations,
            route,
            secondary_view.service_deps,
            secondary_view.service,
        )

    def _create_handler(  # noqa: WPS231
        self,
        service_handler: Literal["list", "detail", "post", "put", "delete"],
        annotations: StrategyReturn,
        service_deps: DependsClass,
        service_type: type[BaseService | SecondaryBaseService],
        response_code: int = 200,
    ) -> Callable:
        response_type = annotations.response

        body_annotation = self._eval_body_annotation(annotations)
        param_annotation = self._eval_params_annotation(annotations)
        pk_annotation = annotations.request.model_pk if annotations.request.model_pk else ExcludeFieldAnnotation
        secondary_pk_annotation = (
            annotations.request.secondary_model_pk if annotations.request.secondary_model_pk else ExcludeFieldAnnotation
        )

        async def inner(  # noqa: WPS430
            service: Annotated[service_type, service_deps],
            model_pk: pk_annotation,
            secondary_model_pk: secondary_pk_annotation,
            body: body_annotation,
            request_params: param_annotation,
        ) -> response_type:
            args = {}
            if model_pk:
                args["model_pk"] = model_pk

            if secondary_model_pk:
                args["secondary_model_pk"] = secondary_model_pk

            if request_params:
                args["request_params"] = request_params

            if body:
                args["body"] = body

            view_handler = getattr(service, service_handler)
            response = await view_handler(**args)

            if response is None:
                return Response(status_code=response_code)

            return response

        return inner

    def _eval_body_annotation(self, annotations: StrategyReturn) -> Annotated | None:
        return Annotated[annotations.request.body, Body()] if annotations.request.body else ExcludeFieldAnnotation

    def _eval_params_annotation(self, annotations: StrategyReturn) -> Annotated | None:
        return (
            Annotated[annotations.request.params, Depends(annotations.request.params.params_deps())]
            if annotations.request.params
            else ExcludeFieldAnnotation
        )
