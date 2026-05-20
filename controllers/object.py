# sarus_client/controllers/object.py
from controllers.base import BaseController
from models.object import ObjectModel
from utils.constants import OBJECTS_CREATE_ENDPOINT, PARAM_NAME_GUID, PARAM_PATH_GUID, PARAM_SIZE_GUID, \
    PARAM_SERVER_GUID


class ObjectController(BaseController):
    def __init__(self, http_client, object_model: ObjectModel, logger=None):
        super().__init__(http_client, logger)
        self.object_model = object_model

    def create_file_object(self, dataset_id, folder_guid, folder_id, class_guid, class_id,
                           file_name, file_size_bytes, relative_path_folder, file_server_id,
                           parameter_group_collection):
        relative_path_full = f"{relative_path_folder}/{file_name}" if relative_path_folder else file_name
        payload = {
            "CreateWithRegularState": False,
            "GuidNearObject": "",
            "ParameterGroupCollection": parameter_group_collection,
            "DatasetObjectCollection": [
                {
                    "AccessLevel": 0,
                    "AdditionalParameters": {"Parameters": []},
                    "AnyReferenceLinksInternal": [],
                    "ApplyChanges": True,
                    "AuthorId": 0,
                    "CancelEdit": False,
                    "ChildObjectsConnection": {
                        "DatasetObjectCollection": [],
                        "ParameterGroupCollection": []
                    },
                    "ClassGuidKey": {
                        "Guid": class_guid,
                        "Id": class_id
                    },
                    "ClientViewId": 0,
                    "CreationDate": "0",
                    "DataLinkedObjects": [],
                    "Deleted": 0,
                    "EditDate": "0",
                    "EditorId": 0,
                    "GroupGuidKey": {
                        "Guid": "",
                        "Id": dataset_id
                    },
                    "GuidKey": {"Guid": "", "Id": 0},
                    "GuidsAccessCategories": [],
                    "HasChildren": 0,
                    "IsActualVersion": 0,
                    "LinkedObjectClassId": 0,
                    "LinkedObjectId": 0,
                    "LinkedObjectsInternal": [],
                    "LinkedObjectsInverted": {
                        "DatasetObjectCollection": [],
                        "ParameterGroupCollection": []
                    },
                    "MasterId": 0,
                    "MasterPrototypeGuidKey": {"Guid": "", "Id": 0},
                    "Options": 0,
                    "Order": 0,
                    "OwnerId": 0,
                    "Parameters": {
                        "Parameters": [
                            {
                                "AdditionalGroupGuid": "",
                                "AdditionalGuids": [],
                                "GroupGuid": "",
                                "Guid": PARAM_NAME_GUID,
                                "IsModified": False,
                                "IsNull": False,
                                "Type": 11,
                                "Value": file_name
                            },
                            {
                                "AdditionalGroupGuid": "",
                                "AdditionalGuids": [],
                                "GroupGuid": "",
                                "Guid": PARAM_PATH_GUID,
                                "IsModified": False,
                                "IsNull": False,
                                "Type": 11,
                                "Value": relative_path_full
                            },
                            {
                                "AdditionalGroupGuid": "",
                                "AdditionalGuids": [],
                                "GroupGuid": "",
                                "Guid": PARAM_SIZE_GUID,
                                "IsModified": False,
                                "IsNull": False,
                                "Type": 7,
                                "Value": str(file_size_bytes)
                            },
                            {
                                "AdditionalGroupGuid": "",
                                "AdditionalGuids": [],
                                "GroupGuid": "",
                                "Guid": PARAM_SERVER_GUID,
                                "IsModified": False,
                                "IsNull": False,
                                "Type": 6,
                                "Value": str(file_server_id)
                            }
                        ]
                    },
                    "ParametersOfLinkedObjects": {"Parameters": []},
                    "ParentGuidKey": {
                        "Guid": folder_guid,
                        "Id": folder_id
                    },
                    "PrivateFolderOwnerId": 0,
                    "RootId": 0,
                    "SourceVersion": 0,
                    "StageId": 0,
                    "State": 0,
                    "SystemType": 0,
                    "Version": 0,
                    "WithChildren": False
                }
            ]
        }
        response = self.http_client.post(OBJECTS_CREATE_ENDPOINT, json=payload)
        self.logger.debug(f"Response status: {response.status_code}")
        self.logger.debug(f"Response text: {response.text[:1000]}")  # первые 1000 символов
        self._handle_response(response)  # если код не 200, вызовет исключение
        resp_json = response.json()
        if "DatasetObjectCollection" not in resp_json:
            self.logger.error(f"Missing DatasetObjectCollection. Full response: {resp_json}")
            raise ValueError("No DatasetObjectCollection in response")
        self.object_model.set_from_response(resp_json)
        self.logger.info(f"Created object with ID: {self.object_model.object_id}")
        return True
