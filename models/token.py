# sarus_client/models/token.py
from dataclasses import dataclass

from models.base import BaseModel


@dataclass
class TokenModel(BaseModel):
    token: str = None

    def set_token(self, token):
        self.token = token

    def __str__(self):
        return f"Token: {self.token}"
