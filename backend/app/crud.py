from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: type[ModelType]) -> None:
        self.model = model

    def get(self, db: Session, object_id: int) -> ModelType | None:
        return db.get(self.model, object_id)

    def list(self, db: Session, *, offset: int, limit: int) -> list[ModelType]:
        statement = select(self.model).offset(offset).limit(limit)
        return list(db.scalars(statement))

    def create(
        self,
        db: Session,
        *,
        data: CreateSchemaType,
        overrides: dict[str, Any] | None = None,
    ) -> ModelType:
        values = data.model_dump(exclude_none=True)
        if overrides:
            values.update(overrides)
        instance = self.model(**values)
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance

    def update(
        self,
        db: Session,
        *,
        instance: ModelType,
        data: UpdateSchemaType,
    ) -> ModelType:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(instance, field, value)
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance

    def delete(self, db: Session, *, instance: ModelType) -> None:
        db.delete(instance)
        db.commit()

