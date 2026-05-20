# sarus_client/models/folder.py
from dataclasses import dataclass

from models.base import BaseModel


@dataclass
class FolderModel(BaseModel):
    id: int = None
    guid: str = None
    relative_path: str = None

    def set_info(self, id_, guid, relative_path):
        self.id = id_
        self.guid = guid
        self.relative_path = relative_path

    def __str__(self):
        return f"Folder ID: {self.id}, GUID: {self.guid}, Path: {self.relative_path}"
