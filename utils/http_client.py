# sarus_client/utils/http_client.py
import requests


class HttpClient:
    def __init__(self, base_url):
        self.session = requests.Session()
        self.base_url = base_url

    def post(self, endpoint, json=None):
        url = self.base_url + endpoint
        return self.session.post(url, json=json)

    def put(self, endpoint, json=None):
        url = self.base_url + endpoint
        return self.session.put(url, json=json)

    def get(self, endpoint, params=None):
        url = self.base_url + endpoint
        return self.session.get(url, params=params)
