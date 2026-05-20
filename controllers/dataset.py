# sarus_client/controllers/dataset.py
from controllers.base import BaseController
from models.dataset import DatasetModel
from utils.constants import DATASET_DESCRIPTION_ENDPOINT


class DatasetController(BaseController):
    def __init__(self, http_client, dataset_model: DatasetModel, logger=None):
        super().__init__(http_client, logger)
        self.dataset_model = dataset_model

    def get_description(self, dataset_id: int):
        params = {"dataset_id": dataset_id}
        response = self.http_client.get(DATASET_DESCRIPTION_ENDPOINT, params=params)
        self._handle_response(response)
        data = response.json()
        self.dataset_model.set_from_response(data)
        self.logger.info(f"Dataset {dataset_id} description loaded")
        return True
