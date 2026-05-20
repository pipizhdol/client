# sarus_client/controllers/folder.py
from controllers.base import BaseController
from models.folder import FolderModel
from utils.constants import OBJECTS_ENDPOINT


class FolderController(BaseController):
    def __init__(self, http_client, folder_model: FolderModel, logger=None):
        super().__init__(http_client, logger)
        self.folder_model = folder_model

    def get_folder_info(self, group_id, object_id):
        payload = {
            "GroupId": group_id,
            "ObjectId": object_id,
            "Versions": False,
            "ParentId": 0,
            "PrototypesMode": False,
            "WithLinkedObjects": False,
            "LoadAnyReferenceLinkObjects": False,
            "LimitCountObjects": 0,
            "ParameterGroupCollection": []
        }
        response = self.http_client.post(OBJECTS_ENDPOINT, json=payload)
        self._handle_response(response)
        data = response.json()
        collection = data.get("DatasetObjectCollection")

        # Если ключа вообще нет в ответе
        if collection is None:
            raise ValueError(f"Неожиданный ответ сервера: нет ключа DatasetObjectCollection. Ответ: {data}")

        # Если сервер вернул пустой список (объект не найден)
        if len(collection) == 0:
            self.logger.error(
                f"Папка не найдена! Сервер вернул пустой список для GroupId={group_id}, ObjectId={object_id}")
            raise ValueError(
                f"Объект (папка) с ID {object_id} в группе {group_id} не существует на сервере или к нему нет доступа.")
        obj = collection[0]
        guid_key = obj.get("GuidKey")
        if not guid_key:
            raise ValueError("No GuidKey in object")
        folder_id = guid_key.get("Id")
        folder_guid = guid_key.get("Guid")
        params_container = obj.get("Parameters")
        if not params_container:
            raise ValueError("No Parameters in object")
        parameters_list = params_container.get("Parameters", [])
        target_guid = "adda774c-dbdf-48ba-bcf6-87bb42a67e90"
        relative_path = None
        for param in parameters_list:
            if param.get("Guid") == target_guid:
                relative_path = param.get("Value")
                break
        if relative_path is None:
            raise ValueError(f"Parameter with GUID {target_guid} not found")
        self.folder_model.set_info(folder_id, folder_guid, relative_path)
        self.logger.info(f"Folder info: {self.folder_model}")
        return True
