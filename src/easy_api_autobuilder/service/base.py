from types import GenericAlias
from typing import Any
from uuid import UUID

from easy_api_autobuilder.constants.constants import (
    ALLOW_NONE_FIELD_NAME,
    FIELD_VALUE_NAME,
    NESTED_PARAM_TEMPLATE,
    PARAM_ORDER_BY_FIELD_NAME,
    PARAM_ORDER_DIRECTION_FIELD_NAME,
    allocated_l,
)
from easy_api_autobuilder.page import Page, PageParams
from easy_api_autobuilder.repo import BaseRepo, SecondaryBaseRepo
from easy_api_autobuilder.schema import BaseModel


class BaseRepoService:
    def __init__(self, repo: BaseRepo):
        self._repo = repo


class ListService(BaseRepoService):
    _output_list: type[Page]
    _inner_data_type: type[BaseModel]

    def _eval_params(self, request_params: PageParams | None) -> tuple[PageParams, Any, Any, Any]:
        if request_params is None:
            return PageParams(), None, None, None

        order_by = getattr(request_params, PARAM_ORDER_BY_FIELD_NAME, None)
        order_direction = getattr(request_params, PARAM_ORDER_DIRECTION_FIELD_NAME, None)

        params = request_params.model_dump(
            exclude={
                ALLOW_NONE_FIELD_NAME,
                PARAM_ORDER_BY_FIELD_NAME,
                PARAM_ORDER_DIRECTION_FIELD_NAME,
                "page",
                "size",
            },
            exclude_unset=True,
        )

        allow_none = getattr(request_params, ALLOW_NONE_FIELD_NAME, allocated_l)
        filters = None

        if not params:
            return request_params, filters, order_by, order_direction

        filters = {}
        for field_name, field_value in params.items():
            if field_name not in allow_none:
                if isinstance(field_value, dict):
                    if not field_value.get(NESTED_PARAM_TEMPLATE.format(field_name, FIELD_VALUE_NAME)):
                        print(field_name, " dissallow")
                        continue
                else:
                    if field_value is None:
                        print(field_name, " dissallow")
                        continue

            filters[field_name] = field_value

        return request_params, filters, order_by, order_direction

    async def list(self, request_params: PageParams | None = None) -> Page:
        """Here must be logic for converting query params to bd limit, offset, filters."""
        request_params, filters, order_by, order_direction = self._eval_params(request_params)

        print(request_params, filters, order_by, order_direction)

        rows_in_db, count = await self._repo.get_by_page(
            page=request_params.page,
            page_size=request_params.size,
            filters=filters,
            order_by=order_by,
            order_dir=order_direction,
        )

        total_pages = count // request_params.size + int((count % request_params.size) > 0)

        return self._output_list(
            page=request_params.page,
            size=request_params.size,
            total_pages=total_pages,
            page_data=[self._inner_data_type.model_validate(row) for row in rows_in_db],
        )


class DetailService(BaseRepoService):
    _output_detail: type[BaseModel]

    async def detail(self, *, model_pk: Any) -> BaseModel:
        row_in_db = await self._repo.get(pkey_val=model_pk)

        return self._output_detail.model_validate(row_in_db)


class DeleteService(BaseRepoService):
    async def delete(self, *, model_pk: Any) -> None:
        await self._repo.delete(pkey_val=model_pk)


class PostService(BaseRepoService):
    _input_create: type[BaseModel]
    _create_response: type[BaseModel]

    async def post(self, body: BaseModel) -> BaseModel:
        assert isinstance(
            body, self._input_create
        ), f"service {self.__class__.__name__} can't recognize {body.__class__.__name__} schema"

        row_id = await self._repo.create(model_data=body.model_dump())
        return self._create_response(id=row_id)


class PutService(BaseRepoService):
    _input_update: type[BaseModel]

    async def put(self, body: BaseModel, *, model_pk: Any) -> None:
        assert isinstance(
            body, self._input_update
        ), f"service {self.__class__.__name__} can't recognize {body.__class__.__name__} schema"

        await self._repo.update(pkey_val=model_pk, model_data=body.put_dump())


class BaseService(
    ListService,
    DetailService,
    DeleteService,
    PostService,
    PutService,
):
    ...


class SecondaryBaseService:
    _output_list: type[BaseModel] | type[list[BaseModel]]

    _input_create: type[BaseModel]

    def __init__(self, repo: SecondaryBaseRepo):
        self._repo = repo

    async def list(self, model_pk: int | UUID, request_params: dict | None = None) -> list[BaseModel]:
        """Here must be logic for converting query params to bd limit, offset, filters."""
        rows_in_db = await self._repo.get_by_first_pk(pkey_val=model_pk)

        if isinstance(self._output_list, GenericAlias):
            return [self._output_list.__args__[0].model_validate(row) for row in rows_in_db]

        return [self._output_list.model_validate(row) for row in rows_in_db]

    async def delete(self, *, model_pk: int | UUID, secondary_model_pk: int | UUID) -> None:
        await self._repo.delete(pkey_val=model_pk, secondary_pkey_val=secondary_model_pk)

    async def post(self, body: BaseModel) -> None:
        assert isinstance(
            body, self._input_create
        ), f"service {self.__class__.__name__} can't recognize {body.__class__.__name__} schema"

        await self._repo.create(model_data=body.model_dump())
