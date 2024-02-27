"""Pydantic custom base model."""
import datetime
import uuid
from enum import StrEnum
from types import GenericAlias, UnionType
from typing import Annotated, Any, Callable

from fastapi import Depends, Query
from pydantic import BaseModel as _BaseModel, ConfigDict
from pydantic.fields import FieldInfo


class BaseModel(_BaseModel):
    model_config = ConfigDict(from_attributes=True)

    def put_dump(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)


class IntegerIdSchema(BaseModel):
    id: int


class UUIDIdSchema(BaseModel):
    id: uuid.UUID


class FilterOperationEnum(StrEnum):
    or_type = "or_type"
    and_type = "and_type"
    between_type = "between_type"


def get_inner_class(type_anno: Any) -> Any:
    if not isinstance(
        type_anno,
        (
            GenericAlias,
            UnionType,
        ),
    ):
        return type_anno

    return get_inner_class(type_anno.__args__[0])


class BaseParams(BaseModel):
    @staticmethod
    def annotate_arg(field_name: str, field: FieldInfo, func_globals: dict) -> str:
        default_arg = "None"
        type_str: str | None = getattr(field.annotation, "__name__", None)
        alias_marker = False
        if isinstance(
            field.annotation,
            (
                GenericAlias,
                UnionType,
            ),
        ):
            type_str = str(field.annotation)
            alias_marker = True

        base_param_marker = False
        if alias_marker:
            print(field.annotation, field.annotation.__args__)
            if not isinstance(
                field.annotation.__args__[0],
                (
                    GenericAlias,
                    UnionType,
                ),
            ):
                base_param_marker = issubclass(field.annotation.__args__[0], BaseParams)

            if base_param_marker:
                type_str = getattr(field.annotation.__args__[0], "__name__", None)
        else:
            base_param_marker = issubclass(field.annotation, BaseParams)

        if type_str is None:
            raise ValueError("type_str must be a type name")

        anno_deps = "Query()" if not base_param_marker else "Depends({0}.params_deps())".format(type_str)
        if anno_deps != "Query()":
            func_globals[type_str] = field.annotation
            if alias_marker:
                func_globals[type_str] = field.annotation.__args__[0]

        if "Enum" in type_str:
            if "." in type_str:
                generic_split = type_str.split("[")
                print(generic_split)
                if len(generic_split) > 1:
                    generic_type_str = generic_split[0]
                    right_union_split = generic_split[1].split("]")
                    inner_split = ", ".join(
                        comma_split.split(".")[-1] for comma_split in right_union_split[0].split(", ")
                    )
                    type_str = "{0}[{1}]{2}".format(generic_type_str, inner_split, "".join(right_union_split[1:]))
                else:
                    type_str = type_str.split(".")[-1]

                type_str = type_str.split(".")[-1]

            enum_type = get_inner_class(field.annotation)
            func_globals[enum_type.__name__] = enum_type
            if "AllowNone" in type_str:
                default_arg = "[]"

            if type_str == FilterOperationEnum.__name__:
                default_arg = "FilterOperationEnum.or_type"

        if "list" in type_str:
            default_arg = "[]"

        return f"{field_name}: Annotated[{type_str}, {anno_deps}] = {default_arg}"

    @classmethod
    def params_deps(cls) -> Callable:
        local_ns = {}
        cls_name = cls.__name__
        func_name = cls_name + "_deps"
        func_globals = {
            f"{cls_name}": cls,
            "Annotated": Annotated,
            "Query": Query,
            "uuid": uuid,
            "datetime": datetime,
            "Depends": Depends,
            "FilterOperationEnum": FilterOperationEnum,
        }

        init_args = []
        func_args = []
        for field_name, field in cls.model_fields.items():
            func_args.append(cls.annotate_arg(field_name, field, func_globals))
            init_args.append(f"{field_name}={field_name}")

        func_args_str = ", ".join(func_args)
        init_args_str = ", ".join(init_args)

        func_text = (
            f"def {func_name}({func_args_str}) -> {cls_name}:"
            f"\n    cls_kwargs = dict({init_args_str})"
            "\n    cls_kwargs = {key: value for key, value in cls_kwargs.items() if value is not None}"
            f"\n    return {cls_name}(**cls_kwargs)"
        )

        exec(func_text, func_globals, local_ns)

        return local_ns[func_name]
