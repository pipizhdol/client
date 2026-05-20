# sarus_client/models/session.py
from dataclasses import dataclass

from models.base import BaseModel


@dataclass
class SessionModel(BaseModel):
    token: str = None
    is_authenticated: bool = False

    def set_token(self, token):
        self.token = token
        self.is_authenticated = True
