# sarus_client/controllers/file_server.py
from controllers.base import BaseController
from models.file_server import FileServerModel
from utils.constants import FILE_SERVERS_ENDPOINT


class FileServerController(BaseController):
    def __init__(self, http_client, file_server_model: FileServerModel, logger=None):
        super().__init__(http_client, logger)
        self.file_server_model = file_server_model
        self.servers_list = []

    def get_servers(self):
        response = self.http_client.get(FILE_SERVERS_ENDPOINT)
        self._handle_response(response)
        data = response.json()
        servers = data.get("FileServers")
        if not servers:
            raise ValueError("No FileServers in response")
        self.servers_list = servers
        self.logger.info(f"Found {len(self.servers_list)} file servers")
        return True

    def select_first(self):
        if not self.servers_list:
            raise ValueError("No servers available")
        srv = self.servers_list[0]
        self.file_server_model.set_server(
            srv.get("ID"),
            srv.get("Host"),
            srv.get("Port"),
            srv.get("Name")
        )
        self.logger.info(f"Selected file server: {self.file_server_model}")
        return True
