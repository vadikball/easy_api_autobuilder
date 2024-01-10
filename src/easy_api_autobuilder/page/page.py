from typing import Generic, TypeVar

from fastapi import Query
from pydantic import Field

from easy_api_autobuilder.schema import BaseModel

PageData = TypeVar("PageData")


class PageParams(BaseModel):
    page: int = Query(default=1, ge=1)
    size: int = Query(default=10, ge=1)


class Page(BaseModel, Generic[PageData]):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=10, ge=1)
    total_pages: int
    page_data: PageData
