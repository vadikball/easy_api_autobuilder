"""Schema from db model factory."""
import datetime
import inspect
from enum import StrEnum
from functools import cached_property
from types import UnionType
from typing import Annotated, Any
from uuid import UUID

from base_enum.enums import OrderDirectionEnum
from constants.constants import (
    PARAM_ORDER_BY_FIELD_NAME,
    PARAM_ORDER_DIRECTION_FIELD_NAME,
    allocated_s,
    default_order_fields,
)
from fastapi import Query
from pydantic import Field, create_model
from schema.base import BaseModel
from sqlalchemy.orm import DeclarativeMeta, InstrumentedAttribute, Relationship

schema_cache: dict[str, type[BaseModel]] = {}
schema_factory_cache: dict[str, DeclarativeMeta] = {}  # {__tablename__: Model}
# models_cache: dict[str, DeclarativeMeta] = {}  # {ModelClassName as str: Model}


filter_types = (
    bool,
    int,
    str,
    datetime.datetime,
    UUID,
)


def eval_type(
    incoming_annotation: type,
) -> type[bool, int, str, datetime.datetime, UUID] | None:
    if isinstance(incoming_annotation, UnionType):
        for filter_type in filter_types:
            if filter_type in incoming_annotation.__args__:
                return filter_type

    if incoming_annotation in filter_types:
        return incoming_annotation

    return None


class SchemaFactory:
    def __new__(cls, model: DeclarativeMeta) -> "SchemaFactory":
        if model.__tablename__ in schema_factory_cache:
            return schema_factory_cache[model.__tablename__]

        instance = super().__new__(cls)
        instance.__init__(model)
        return instance

    def __init__(self, model: DeclarativeMeta):
        if model.__tablename__ in schema_factory_cache:
            return

        self._model = model
        self._model_annotations = inspect.get_annotations(self._model)
        schema_factory_cache[self._model.__tablename__] = self

    @property
    def _pure_name(self) -> str:
        return self._model.__name__.split("Model")[0]

    def create_params_from_model(
        self, primary_schema: type[BaseModel] | None = None, name_postfix: str = "List"
    ) -> tuple[type[BaseModel], Any]:
        if primary_schema is None:
            primary_schema = BaseModel

        schema_annotations = {}
        order_fields = []
        allow_none = []

        for field_name, annotation in self._model_annotations.items():
            annotation_type = eval_type(annotation)
            if annotation_type is None:
                continue

            if annotation_type is not bool:
                order_fields.append(field_name)

            allow_none.append(field_name)

            schema_annotations[field_name] = (
                Annotated[annotation_type | None, Query()],
                None,
            )

        allow_none_annotation = None

        if allow_none:
            AllowNoneEnum = StrEnum(
                "{0}{1}".format(self._pure_name, "AllowNoneEnum"),
                {allow_none_field: allow_none_field for allow_none_field in allow_none},
            )
            allow_none_annotation = Annotated[list[AllowNoneEnum], Query()]

        if order_fields:
            OrderEnum = StrEnum(
                "{0}{1}".format(self._pure_name, "OrderByEnum"),
                {
                    order_field_name: order_field_name
                    for order_field_name in order_fields
                },
            )

            default_enum = OrderEnum(OrderEnum._member_names_[0])
            for field in default_order_fields:
                if field in OrderEnum._member_names_:
                    default_enum = OrderEnum(field)
                    break

            print(default_enum)
            schema_annotations[PARAM_ORDER_BY_FIELD_NAME] = (
                Annotated[OrderEnum, Query(default_enum)],
                default_enum,
            )
            schema_annotations[PARAM_ORDER_DIRECTION_FIELD_NAME] = (
                OrderDirectionEnum,
                Query(OrderDirectionEnum.ASC),
            )

        schema_name = "{0}{1}{2}".format(self._pure_name, "Params", name_postfix)
        schema = create_model(
            schema_name, **schema_annotations, __base__=primary_schema
        )
        schema_cache[schema_name] = schema

        print(f"{self._model.__tablename__}, {schema_name}\n{schema_annotations}\n\n")

        return schema, allow_none_annotation

    def create_schema_from_model(
        self,
        defaults: dict[str, Any] | None = None,
        excluded: set | None = None,
        nested: bool = True,
        name_postfix: str | None = None,
        put: bool = False,
        included: set | None = None,
    ) -> type[BaseModel]:
        schema_name = "".join((self._pure_name, "Schema", name_postfix))

        if schema_name in schema_cache:
            return schema_cache[schema_name]

        defaults = defaults or allocated_s
        excluded = excluded or allocated_s
        included = included or allocated_s

        schema_annotations = self._create_schema_annotations(
            defaults, excluded, nested, put, included
        )

        print(f"{self._model.__tablename__}, {schema_name}\n{schema_annotations}\n\n")

        schema = create_model(schema_name, **schema_annotations, __base__=BaseModel)
        schema_cache[schema_name] = schema

        return schema

    @cached_property
    def pk_annotations(self) -> tuple:
        primary_keys = []
        for field_name, annotation in self._model_annotations.items():
            model_field: InstrumentedAttribute = getattr(self._model, field_name)
            if hasattr(model_field, "primary_key") and model_field.primary_key:
                primary_keys.append(annotation)

        return tuple(primary_keys)

    def _create_schema_annotations(
        self,
        defaults: dict[str, Any] | None,
        excluded: set,
        nested: bool,
        put: bool,
        included: set,
    ) -> dict[str, Any]:
        schema_annotations = {}
        for field_name, annotation in self._model_annotations.items():
            if field_name in excluded:
                continue

            model_field: InstrumentedAttribute = getattr(self._model, field_name)

            if isinstance(model_field.property, Relationship):
                if not nested and field_name not in included:
                    continue

                annotation, default_value = self._resolve_nested(model_field.property)

            else:
                if put:
                    if hasattr(model_field, "primary_key") and model_field.primary_key:
                        continue

                    default_value = None

                else:
                    if model_field.default is None:
                        if model_field.nullable is False:
                            default_value = ...
                        else:
                            default_value = None

                    elif field_name in defaults:
                        default_value = defaults[field_name]
                    else:
                        if model_field.default.is_callable:
                            default_value = Field(
                                default_factory=model_field.default.arg
                            )
                        else:
                            default_value = model_field.default.arg

            schema_annotations[field_name] = (
                annotation,
                default_value,
            )

        return schema_annotations

    def _resolve_nested(self, field_property: Relationship):
        sub_model = field_property.argument
        if isinstance(sub_model, str):
            sub_model = field_property.entity.entity

        nested_schema_factory = SchemaFactory(sub_model)

        if field_property.uselist:
            annotation = list[
                nested_schema_factory.create_schema_from_model(name_postfix="List")
            ]
            default_value = Field(default_factory=list)
        else:
            annotation = (
                nested_schema_factory.create_schema_from_model(name_postfix="Detail")
                | None
            )
            default_value = None

        return annotation, default_value
