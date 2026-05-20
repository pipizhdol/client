# sarus_client/controllers/base.py
import logging
from typing import Optional

from utils.exceptions import APIError
from utils.http_client import HttpClient


class BaseController:
    def __init__(self, http_client: HttpClient, logger: Optional[logging.Logger] = None):
        self.http_client = http_client
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def _log_request(self, method: str, endpoint: str, **kwargs):
        self.logger.debug(f"{method} {endpoint} {kwargs}")

    def _handle_response(self, response, expected_status=200):
        if response.status_code != expected_status:
            raise APIError(response.status_code, response.text)
        return response
