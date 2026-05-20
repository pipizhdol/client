# sarus_client/controllers/checkin.py
from controllers.base import BaseController
from utils.constants import CHECKIN_ENDPOINT


class CheckinController(BaseController):
    def checkin(self, dataset_object_collection, parameter_group_collection):
        payload = {
            "CancelCheckIn": False,
            "Comment": "",
            "DatasetObjectCollection": dataset_object_collection,
            "ParameterGroupCollection": parameter_group_collection
        }
        response = self.http_client.put(CHECKIN_ENDPOINT, json=payload)
        self._handle_response(response)
        self.logger.info("Check-in completed")
        return True
