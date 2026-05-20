# sarus_client/controllers/class_controller.py
import re

from controllers.base import BaseController
from models.class_model import ClassModel
from utils.constants import CLASSES_ENDPOINT


class ClassController(BaseController):
    def __init__(self, http_client, class_model: ClassModel, logger=None):
        super().__init__(http_client, logger)
        self.class_model = class_model
        self.classes_list = []

    def get_classes(self, dataset_id):
        url = f"{CLASSES_ENDPOINT}/{dataset_id}"
        response = self.http_client.get(url)
        self._handle_response(response)
        data = response.json()

        main_doc = data.get("_mainDocument")
        if not main_doc:
            raise ValueError("No _mainDocument in response")
        classes_info = main_doc.get("_datasetClassesInfoCollection")
        if not classes_info:
            raise ValueError("No _datasetClassesInfoCollection")

        self.classes_list = []
        for idx, cls in enumerate(classes_info):
            # Берём ID и GUID из _guidKey
            guid_key = cls.get("_guidKey") or {}
            class_id = guid_key.get("Id")
            class_guid = guid_key.get("Guid")
            class_name = cls.get("_name") or ""

            if not class_id or int(class_id) == 0:
                self.logger.warning(f"Класс {idx} не имеет корректного _guidKey.Id: {cls}")
                continue

            # Извлечение расширений из _attributes
            attributes = cls.get("_attributes", "")
            extensions = []
            if attributes and attributes != "0":
                found = re.findall(r"<Extension>(.*?)</Extension>", attributes, re.IGNORECASE)
                if found:
                    extensions = [ext.strip().lower().lstrip('.') for ext in found]
                else:
                    parts = attributes.replace(',', ' ').split()
                    extensions = [p.strip().lower().lstrip('.') for p in parts if p.strip()]
            extensions = list(set(extensions))

            self.classes_list.append({
                "id": int(class_id),
                "guid": class_guid,
                "name": class_name,
                "extensions": extensions
            })

        if not self.classes_list:
            raise ValueError("No classes found with valid ID")
        self.logger.info(f"Found {len(self.classes_list)} classes")
        return True

    def find_class_by_extension(self, ext):
        ext = ext.lower().strip()
        for cls in self.classes_list:
            if ext in cls["extensions"]:
                return cls
        self.logger.warning(f"No class for extension '{ext}'")
        return None

    def get_class_by_id(self, class_id):
        for cls in self.classes_list:
            if cls["id"] == class_id:
                return cls
        return None

    def get_folder_class(self):
        cls = self.get_class_by_id(1)
        if cls:
            return cls
        for cls in self.classes_list:
            if "папка" in cls["name"].lower():
                return cls
        for cls in self.classes_list:
            if not cls["extensions"]:
                return cls
        return self.classes_list[0] if self.classes_list else None

    def select_class_by_extension(self, ext):
        cls = self.find_class_by_extension(ext)
        if cls:
            self.class_model.set_class(cls["id"], cls["guid"], cls["name"], cls["extensions"])
            return True
        return False
