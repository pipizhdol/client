# sarus_client/models/class_model.py
from dataclasses import dataclass, field
from typing import List

from models.base import BaseModel


@dataclass
class ClassModel(BaseModel):
    id: int = None
    guid: str = None
    name: str = None
    extensions: List[str] = field(default_factory=list)

    def set_class(self, id_, guid, name, extensions):
        self.id = id_
        self.guid = guid
        self.name = name
        self.extensions = extensions

    def __str__(self):
        return f"Class ID: {self.id}, GUID: {self.guid}, Name: {self.name}, Extensions: {', '.join(self.extensions)}"
