# sarus_client/models/file_server.py
from dataclasses import dataclass

from models.base import BaseModel


@dataclass
class FileServerModel(BaseModel):
    id: int = None
    host: str = None
    port: int = None
    name: str = None

    def set_server(self, id_, host, port, name):
        self.id = id_
        self.host = host
        self.port = port
        self.name = name

    def __str__(self):
        return f"FileServer ID: {self.id}, Host: {self.host}:{self.port}, Name: {self.name}"
