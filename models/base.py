# sarus_client/models/base.py

from dataclasses import dataclass, asdict


@dataclass
class BaseModel:
    """Базовый класс для всех моделей данных."""

    def to_dict(self) -> dict:
        """Преобразовать модель в словарь."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        """Создать модель из словаря."""
        return cls(**data)
