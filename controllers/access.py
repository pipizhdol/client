# sarus_client/controllers/access.py
from controllers.base import BaseController
from utils.constants import ACCESS_LEVELS_SESSION_ENDPOINT


class AccessController(BaseController):
    def set_mandatory_level(self, level: int = 0):
        payload = {
            "SessionAccessCategories": [],
            "SessionMandatoryAccessLevel": level
        }
        response = self.http_client.put(ACCESS_LEVELS_SESSION_ENDPOINT, json=payload)
        self._handle_response(response)
        self.logger.info(f"Mandatory access level set to {level}")
        return True
