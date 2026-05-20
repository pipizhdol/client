# sarus_client/controllers/auth.py
from controllers.base import BaseController
from models.session import SessionModel
from utils.constants import AUTH_ENDPOINT
from utils.exceptions import AuthError


class AuthController(BaseController):
    def __init__(self, http_client, session_model: SessionModel, logger=None):
        super().__init__(http_client, logger)
        self.session_model = session_model

    def authenticate(self, login: str, password: str, **kwargs):
        payload = {
            "Login": login,
            "Password": password,
            "Version": kwargs.get("version", ""),
            "MACAddress": kwargs.get("mac_address", ""),
            "Authentication": kwargs.get("authentication", 0),
            "AppInstanceID": kwargs.get("app_instance_id", "12687"),
            "FQDN": kwargs.get("fqdn", ""),
            "Hostname": kwargs.get("hostname", ""),
            "ClientType": kwargs.get("client_type", 0)
        }
        self._log_request("POST", AUTH_ENDPOINT, payload=payload)
        response = self.http_client.post(AUTH_ENDPOINT, json=payload)
        self._handle_response(response)

        if 'user' not in response.cookies:
            raise AuthError("Cookie 'user' not found after authentication")
        token = response.cookies['user']
        self.session_model.set_token(token)
        self.logger.info("Authentication successful")
        return True
