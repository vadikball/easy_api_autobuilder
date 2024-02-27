"""Common schema creation strategy."""
from dataclasses import dataclass
from functools import cached_property
from typing import Any
from uuid import UUID

from fastapi import Response

from easy_api_autobuilder.arguments import SchemaCreationArguments
from easy_api_autobuilder.page import Page, PageParams
from easy_api_autobuilder.schema.base import BaseModel, BaseParams, IntegerIdSchema, UUIDIdSchema
from easy_api_autobuilder.schema.factory import SchemaFactory


def post_response_schema_factory(
    model_pk: type[int | UUID],
) -> type[IntegerIdSchema | UUIDIdSchema]:
    if model_pk is int:
        return IntegerIdSchema

    return UUIDIdSchema


@dataclass
class RequestTypes:
    model_pk: type[int | UUID] | None
    params: type[BaseParams] | None
    body: type[BaseModel] | None
    secondary_model_pk: type[int | UUID] | None = None


@dataclass
class StrategyReturn:
    request: RequestTypes
    response: type[BaseModel] | type[list[BaseModel]] | type[Response]
    inner_response_type: type[BaseModel] | None = None


class BaseSchemaCreationStrategy:
    def __init__(
        self,
        schema_factory: SchemaFactory,
        arguments: SchemaCreationArguments | None = None,
    ):
        self._schema_factory = schema_factory
        self.arguments = SchemaCreationArguments() if arguments is None else arguments


class SchemaCreationStrategy(BaseSchemaCreationStrategy):
    @cached_property
    def list(self) -> StrategyReturn:
        return_schema = self._schema_factory.create_schema_from_model(
            defaults=self.arguments.list_args.defaults,
            excluded=self.arguments.list_args.excluded,
            name_postfix=self.arguments.list_args.name_postfix,
            nested=self.arguments.list_args.nested,
            put=self.arguments.list_args.put,
            included=self.arguments.list_args.included,
        )
        params_schema = self._schema_factory.create_params_from_model(PageParams)
        return StrategyReturn(
            request=RequestTypes(
                model_pk=None,
                params=params_schema,
                body=None,
            ),
            response=Page[list[return_schema]],
            inner_response_type=return_schema,
        )

    @cached_property
    def detail(self) -> StrategyReturn:
        return StrategyReturn(
            request=RequestTypes(model_pk=self._schema_factory.pk_annotations[0], params=None, body=None),
            response=self._schema_factory.create_schema_from_model(
                defaults=self.arguments.detail_args.defaults,
                excluded=self.arguments.detail_args.excluded,
                name_postfix=self.arguments.detail_args.name_postfix,
                nested=self.arguments.detail_args.nested,
                put=self.arguments.detail_args.put,
                included=self.arguments.detail_args.included,
            ),
        )

    @cached_property
    def post(self) -> StrategyReturn:
        return StrategyReturn(
            request=RequestTypes(
                model_pk=None,
                params=None,
                body=self._schema_factory.create_schema_from_model(
                    defaults=self.arguments.post_args.defaults,
                    excluded=self.arguments.post_args.excluded,
                    name_postfix=self.arguments.post_args.name_postfix,
                    nested=self.arguments.post_args.nested,
                    put=self.arguments.post_args.put,
                ),
            ),
            response=post_response_schema_factory(self._schema_factory.pk_annotations[0]),
        )

    @cached_property
    def put(self) -> StrategyReturn:
        return StrategyReturn(
            request=RequestTypes(
                model_pk=self._schema_factory.pk_annotations[0],
                params=None,
                body=self._schema_factory.create_schema_from_model(
                    defaults=self.arguments.put_args.defaults,
                    excluded=self.arguments.put_args.excluded,
                    name_postfix=self.arguments.put_args.name_postfix,
                    nested=self.arguments.put_args.nested,
                    put=self.arguments.put_args.put,
                ),
            ),
            response=Response,
        )

    @cached_property
    def delete(self) -> StrategyReturn:
        return StrategyReturn(
            request=self.detail.request,
            response=Response,
        )


class SecondarySchemaCreationStrategy(BaseSchemaCreationStrategy):
    @cached_property
    def list(self) -> StrategyReturn:
        return StrategyReturn(
            request=RequestTypes(model_pk=self._schema_factory.pk_annotations[0], params=None, body=None),
            response=list[
                self._schema_factory.create_schema_from_model(
                    defaults=self.arguments.list_args.defaults,
                    excluded=self.arguments.list_args.excluded,
                    name_postfix=self.arguments.list_args.name_postfix,
                    nested=self.arguments.list_args.nested,
                    put=self.arguments.list_args.put,
                    included=self.arguments.list_args.included,
                )
            ],
        )

    @cached_property
    def post(self) -> StrategyReturn:
        return StrategyReturn(
            request=RequestTypes(
                model_pk=None,
                params=None,
                body=self._schema_factory.create_schema_from_model(
                    defaults=self.arguments.post_args.defaults,
                    excluded=self.arguments.post_args.excluded,
                    name_postfix=self.arguments.post_args.name_postfix,
                    nested=self.arguments.post_args.nested,
                    put=self.arguments.post_args.put,
                ),
            ),
            response=Response,
        )

    @cached_property
    def delete(self) -> StrategyReturn:
        secondary_pk = self._schema_factory.pk_annotations[1] if len(self._schema_factory.pk_annotations) > 1 else None

        return StrategyReturn(
            request=RequestTypes(
                model_pk=self._schema_factory.pk_annotations[0],
                params=None,
                body=None,
                secondary_model_pk=secondary_pk,
            ),
            response=Response,
        )
