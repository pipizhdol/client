# sarus_client/controllers/folder_create.py
from controllers.base import BaseController
from utils.constants import OBJECTS_CREATE_ENDPOINT, PARAM_NAME_GUID, PARAM_PATH_GUID


class FolderCreateController(BaseController):
    def create_folder(self, dataset_id, parent_guid, parent_id, class_guid, class_id,
                      folder_name, relative_path, parameter_group_collection):
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
                                "Value": folder_name
                            },
                            {
                                "AdditionalGroupGuid": "",
                                "AdditionalGuids": [],
                                "GroupGuid": "",
                                "Guid": PARAM_PATH_GUID,
                                "IsModified": False,
                                "IsNull": False,
                                "Type": 11,
                                "Value": relative_path
                            }
                        ]
                    },
                    "ParametersOfLinkedObjects": {"Parameters": []},
                    "ParentGuidKey": {
                        "Guid": parent_guid,
                        "Id": parent_id
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
        self.logger.debug(f"Response text: {response.text[:500]}")
        self._handle_response(response)
        data = response.json()

        # Проверяем наличие DatasetObjectCollection
        collection = data.get("DatasetObjectCollection")
        if not collection:
            # Некоторые версии API могут возвращать объект напрямую без обёртки
            # или ошибку. Выведем содержимое для анализа.
            self.logger.error(f"Unexpected response structure: {data}")
            raise ValueError(f"No DatasetObjectCollection in response. Keys: {data.keys()}")

        obj = collection[0]
        guid_key = obj.get("GuidKey")
        if not guid_key:
            raise ValueError("Missing GuidKey in object")
        folder_id = guid_key.get("Id")
        folder_guid = guid_key.get("Guid")
        self.logger.info(f"Created folder: {folder_name} (ID: {folder_id})")
        return folder_id, folder_guid

    def checkin_folder(self, dataset_id: int, folder_id: int, folder_guid: str):
        """Подтверждает создание папки (выход из режима редактирования)."""
        payload = {
            "CancelCheckIn": False,
            "Comment": "",
            "DatasetObjectCollection": [{
                "GuidKey": {"Id": folder_id, "Guid": folder_guid},
                "GroupGuidKey": {"Id": dataset_id, "Guid": ""},
                "ParentGuidKey": {"Id": 0, "Guid": ""},
                "ClassGuidKey": {"Id": 0, "Guid": ""},
                "Parameters": {"Parameters": []}
            }],
            "ParameterGroupCollection": []
        }
        response = self.http_client.put("/objects/edit/checkin", json=payload)
        self._handle_response(response)
        self.logger.info(f"Check-in выполнен для папки {folder_id}")
