# sarus_client/models/object.py
from dataclasses import dataclass, field
from typing import Dict, Any

from models.base import BaseModel


@dataclass
class ObjectModel(BaseModel):
    object_id: int = None
    object_guid: str = None
    full_response: Dict[str, Any] = field(default_factory=dict)

    def set_from_response(self, response_json):
        self.full_response = response_json
        collection = response_json.get("DatasetObjectCollection")
        if collection and len(collection) > 0:
            obj = collection[0]
            guid_key = obj.get("GuidKey")
            if guid_key:
                self.object_id = guid_key.get("Id")
                self.object_guid = guid_key.get("Guid")
