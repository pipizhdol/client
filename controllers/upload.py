# sarus_client/controllers/upload.py
import os

import requests

from controllers.base import BaseController


class UploadController(BaseController):
    def upload_file(self, file_server_host, file_server_port, token, file_path):
        url = f"http://{file_server_host}:{file_server_port}/file/{token}"
        self.logger.info(f"Uploading file to {url}")
        try:
            file_size = os.path.getsize(file_path)
            self.logger.debug(f"File size: {file_size} bytes")
            headers = {'Content-Type': 'application/octet-stream'}
            with open(file_path, 'rb') as f:
                response = requests.put(url, data=f, headers=headers)
            if response.status_code not in (200, 201, 204):
                raise Exception(f"Upload failed: {response.status_code} {response.text}")
            self.logger.info("File uploaded successfully")
            return True
        except Exception as e:
            self.logger.error(f"Upload error: {e}")
            raise
