# sarus_client/controllers/token.py
import hashlib

from controllers.base import BaseController
from models.token import TokenModel
from utils.constants import TOKEN_ENDPOINT


class TokenController(BaseController):
    def __init__(self, http_client, token_model: TokenModel, logger=None):
        super().__init__(http_client, logger)
        self.token_model = token_model

    def get_token(self, object_id, file_path, file_server_host, file_server_port):
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
        except Exception as e:
            self.logger.error(f"Error reading file for MD5: {e}")
            raise
        file_hash = hash_md5.hexdigest()
        self.logger.debug(f"MD5 hash: {file_hash}")
        params = {
            "id": object_id,
            "version_id": 1,
            "command_id": 3,
            "sourceVersion_id": 1,
            "hash": file_hash,
            "host": file_server_host,
            "port": file_server_port
        }
        response = self.http_client.get(TOKEN_ENDPOINT, params=params)
        self._handle_response(response)
        data = response.json()
        token = data.get("Token")
        if not token:
            raise ValueError("No Token in response")
        self.token_model.set_token(token)
        self.logger.info("Token obtained")
        return True
