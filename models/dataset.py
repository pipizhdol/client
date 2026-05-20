# sarus_client/models/dataset.py
from dataclasses import dataclass, field
from typing import List, Dict, Any

from models.base import BaseModel


@dataclass
class DatasetModel(BaseModel):
    raw_response: Dict[str, Any] = field(default_factory=dict)
    parameter_group_collection: List[Any] = field(default_factory=list)

    def set_from_response(self, response_json):
        self.raw_response = response_json
        self.parameter_group_collection = response_json.get("ParameterGroupCollection", [])
