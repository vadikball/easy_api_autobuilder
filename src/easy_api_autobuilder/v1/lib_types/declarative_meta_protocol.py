from typing import Protocol


class DeclarativeMetaProtocol(Protocol):
    __tablename__: str
