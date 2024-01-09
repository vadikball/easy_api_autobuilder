"""Base repo implementation."""
from typing import Any

from base_enum.enums import OrderDirectionEnum
from constants.constants import allocated_l, default_order_fields
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import DeclarativeMeta


class BaseRepo:
    """Base repo for models."""

    _cls_model: DeclarativeMeta

    def __init__(self, session: AsyncSession):
        self._session = session

    async def bulk_create(self, *, model_data: list[dict[str, Any]]) -> Any:
        bulk_query = insert(self._cls_model).values(model_data)

        res = await self._session.execute(bulk_query)
        await self._session.commit()
        return res.inserted_primary_key

    async def create(self, *, model_data: dict[str, Any]) -> Any:
        """Create object."""
        query = insert(self._cls_model).values(**model_data)

        res = await self._session.execute(query)
        await self._session.commit()
        return res.inserted_primary_key[0]

    async def update(
        self,
        *,
        pkey_val: Any,
        model_data: dict[str, Any],
    ) -> None:
        """Update object by primary key."""
        primary_key = inspect(self._cls_model).primary_key[0]
        query = (
            update(self._cls_model)
            .where(primary_key == pkey_val)
            .values(**model_data)
            .execution_options(synchronize_session="fetch")
        )

        await self._session.execute(query)
        await self._session.commit()

    async def bulk_update_by_field(
        self,
        *,
        field_name: str,
        field_values: list,
        model_data: dict[str, Any],
    ) -> None:
        """Update objects by field."""
        bulk_query = (
            update(self._cls_model)
            .where(getattr(self._cls_model, field_name).in_(field_values))
            .values(**model_data)
            .execution_options(synchronize_session="fetch")
        )

        await self._session.execute(bulk_query)
        await self._session.commit()

    async def delete(self, *, pkey_val: Any) -> None:
        """Delete object by primary key value."""
        primary_key = inspect(self._cls_model).primary_key[0].name
        query = (
            delete(self._cls_model)
            .where(getattr(self._cls_model, primary_key) == pkey_val)
            .execution_options(synchronize_session="fetch")
        )

        await self._session.execute(query)
        await self._session.commit()

    async def get(self, *, pkey_val: Any) -> Any:
        """Get object by primary key."""
        primary_key = inspect(self._cls_model).primary_key[0]
        query = select(self._cls_model).where(primary_key == pkey_val)

        rows = await self._session.execute(query)
        return rows.scalars().one()

    async def get_or_none(self, *, pkey_val: Any) -> Any:
        """Get object by primary key or none."""
        primary_key = inspect(self._cls_model).primary_key[0]
        query = select(self._cls_model).where(primary_key == pkey_val)

        rows = await self._session.execute(query)
        return rows.scalar()

    async def all(
        self,
    ) -> Any:
        """Get all objects by db model."""
        query = select(self._cls_model)

        rows = await self._session.execute(query)
        return rows.scalars().all()

    def _eval_filters(self, filters: dict[str, Any] | None) -> list:
        if filters is None:
            return allocated_l

        filter_exp = []
        for field_name, field_value in filters.items():
            filter_exp.append(getattr(self._cls_model, field_name) == field_value)

        return filter_exp

    def _default_order(self) -> Any:
        order_exp = None

        for field in default_order_fields:
            try:
                order_exp = getattr(self._cls_model, field)
            except AttributeError:
                continue
            else:
                break

        return order_exp

    def _eval_order(
        self, order_by: str | None, order_dir: OrderDirectionEnum | None
    ) -> Any:
        if order_by is None:
            return self._default_order()

        order_exp = getattr(self._cls_model, order_by)
        if order_dir == OrderDirectionEnum.DESC:
            order_exp = order_exp.desc()

        return order_exp

    async def get_by_page(
        self,
        page: int | None,
        page_size: int | None,
        filters: dict[str, Any] | None,
        order_by: str | None,
        order_dir: OrderDirectionEnum | None,
    ) -> tuple[Any, int]:
        if page is None:
            page = 1

        if page_size is None:
            page_size = 10

        print(filters)
        filters_exp = self._eval_filters(filters)
        print(filters_exp)

        order_exp = self._eval_order(order_by, order_dir)

        limit = page_size
        offset = page_size * (page - 1)

        count_query = select(func.count()).select_from(self._cls_model).order_by(None)
        query = select(self._cls_model)

        if filters_exp:
            count_query = count_query.where(*filters_exp)
            query = query.where(*filters_exp)

        print(count_query)
        count_result = await self._session.execute(count_query)
        count = count_result.scalar()
        if not count:
            return tuple(), count

        if order_exp is not None:
            query = query.order_by(order_exp)

        query = query.limit(limit).offset(offset)
        print(query)
        rows = await self._session.execute(query)

        return rows.scalars().all(), count

    async def get_by_field(self, *, field: str, field_value: Any) -> Any:
        """Return objects from db with condition field=val."""
        query = select(self._cls_model).where(
            getattr(self._cls_model, field) == field_value
        )

        rows = await self._session.execute(query)
        return rows.scalars().all()

    async def get_by_field_or_none(self, *, field: str, field_value: Any) -> Any:
        """Return objects from db with condition field=val."""
        custom_query = select(self._cls_model).where(
            getattr(self._cls_model, field) == field_value
        )

        rows = await self._session.execute(custom_query)
        return rows.scalar()


class SecondaryBaseRepo:
    """Base repo for M2M models."""

    _cls_model: DeclarativeMeta

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, *, model_data: dict[str, Any]) -> Any:
        """Create object."""
        query = insert(self._cls_model).values(**model_data)

        await self._session.execute(query)
        await self._session.commit()

    async def delete(self, *, pkey_val: Any, secondary_pkey_val: Any) -> None:
        """Delete object by primary key values."""
        p_keys = inspect(self._cls_model).primary_key
        first_primary_key = p_keys[0].name
        secondary_primary_key = p_keys[1].name

        print(first_primary_key)
        print(secondary_primary_key)

        query = (
            delete(self._cls_model)
            .where(
                getattr(self._cls_model, first_primary_key) == pkey_val,
                getattr(self._cls_model, secondary_primary_key) == secondary_pkey_val,
            )
            .execution_options(synchronize_session="fetch")
        )

        print(query)
        await self._session.execute(query)
        await self._session.commit()

    async def all(
        self,
    ) -> Any:
        """Get all objects by db model."""
        query = select(self._cls_model)

        rows = await self._session.execute(query)
        return rows.scalars().all()

    async def get_by_first_pk(self, *, pkey_val: Any) -> Any:
        """Return objects from db with condition field=val."""
        first_primary_key = inspect(self._cls_model).primary_key[0].name

        query = select(self._cls_model).where(
            getattr(self._cls_model, first_primary_key) == pkey_val
        )

        rows = await self._session.execute(query)
        return rows.scalars().all()

    async def get_by_field(self, *, field: str, field_value: Any) -> Any:
        """Return objects from db with condition field=val."""
        query = select(self._cls_model).where(
            getattr(self._cls_model, field) == field_value
        )

        rows = await self._session.execute(query)
        return rows.scalars().all()

    async def get_by_field_or_none(self, *, field: str, field_value: Any) -> Any:
        """Return objects from db with condition field=val."""
        custom_query = select(self._cls_model).where(
            getattr(self._cls_model, field) == field_value
        )

        rows = await self._session.execute(custom_query)
        return rows.scalar()
