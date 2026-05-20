# sarus_client/controllers/link.py
from controllers.base import BaseController
from utils.constants import LINK_ENDPOINT


class LinkController(BaseController):
    def create_link(self, dataset_id_slave, object_id_slave, parent_id_master, table_name):
        payload = {
            "DatasetID": dataset_id_slave,
            "ObjectsList": [
                {
                    "ObjectID": object_id_slave,
                    "ParentID": parent_id_master
                }
            ],
            "TableName": table_name
        }
        response = self.http_client.post(LINK_ENDPOINT, json=payload)
        self._handle_response(response)
        self.logger.info(f"Link created: slave {dataset_id_slave}:{object_id_slave} -> master {parent_id_master}")
        return True
