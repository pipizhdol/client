# sarus_client/core/client.py
import logging
import os
from typing import Dict, Any, Tuple, Optional

from config import default_config
from controllers.access import AccessController
from controllers.auth import AuthController
from controllers.checkin import CheckinController
from controllers.class_controller import ClassController
from controllers.dataset import DatasetController
from controllers.file_server import FileServerController
from controllers.folder import FolderController
from controllers.folder_create import FolderCreateController
from controllers.link import LinkController
from controllers.object import ObjectController
from controllers.token import TokenController
from controllers.upload import UploadController
from models.class_model import ClassModel
from models.dataset import DatasetModel
from models.file_server import FileServerModel
from models.folder import FolderModel
from models.object import ObjectModel  # <-- добавлен импорт
from models.session import SessionModel
from models.token import TokenModel  # <-- добавлен импорт
from utils.http_client import HttpClient
from utils.constants import OBJECTS_ENDPOINT, PARAM_NAME_GUID
from utils.constants import DATASET_CATALOG_ENDPOINT
from utils.constants import DATASET_DESCRIPTION_ENDPOINT


class SarusClient:
    """Единый клиент для работы с САРУС, кэширует данные и управляет сессией."""

    def __init__(self, server: str, log_callback=None):
        self.logger = logging.getLogger("SarusClient")
        if log_callback:
            handler = logging.Handler()
            handler.emit = lambda record: log_callback(handler.format(record))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

        if not server.startswith("http"):
            server = "http://" + server
        self.base_url = f"{server}/v1"
        self.http_client = HttpClient(self.base_url)

        # Модели для хранения состояния
        self.session_model = SessionModel()
        self.dataset_model = DatasetModel()
        self.folder_model = FolderModel()
        self.file_server_model = FileServerModel()
        self.class_model = ClassModel()
        self.object_model = ObjectModel()  # <-- инициализация модели
        self.token_model = TokenModel()  # <-- инициализация модели

        # Контроллеры
        self.auth = AuthController(self.http_client, self.session_model, self.logger)
        self.access = AccessController(self.http_client, self.logger)
        self.dataset = DatasetController(self.http_client, self.dataset_model, self.logger)
        self.folder = FolderController(self.http_client, self.folder_model, self.logger)
        self.file_server = FileServerController(self.http_client, self.file_server_model, self.logger)
        self.class_ctrl = ClassController(self.http_client, self.class_model, self.logger)
        self.object = ObjectController(self.http_client, self.object_model, self.logger)
        self.token = TokenController(self.http_client, self.token_model, self.logger)
        self.upload = UploadController(self.logger)
        self.checkin = CheckinController(self.http_client, self.logger)
        self.folder_create = FolderCreateController(self.http_client, self.logger)
        self.link = LinkController(self.http_client, self.logger)

        # Кэши для данных справочников
        self._dataset_cache = {}  # dataset_id -> (dataset_model, class_list, file_server_id, ...)
        self._is_authenticated = False
        self._table_names_cache = {}

    def authenticate(self, login: str = None, password: str = None) -> bool:
        """Авторизация и установка мандатного доступа."""
        if login is None:
            login = default_config.login
        if password is None:
            password = default_config.password

        self.auth.authenticate(login, password)
        self.access.set_mandatory_level()
        self._is_authenticated = True
        self.logger.info("Authenticated and mandatory level set")
        return True

    def _ensure_authenticated(self):
        if not self._is_authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

    def _load_dataset_info(self, dataset_id: int) -> dict:
        if dataset_id in self._dataset_cache:
            return self._dataset_cache[dataset_id]

        self._ensure_authenticated()

        # Загружаем описание справочника
        self.dataset.get_description(dataset_id)
        desc_keys = list(self.dataset_model.raw_response.keys())
        self.logger.debug(f"Dataset {dataset_id} description keys: {desc_keys}")
        # Загружаем классы
        self.class_ctrl.get_classes(dataset_id)
        # Загружаем файловые серверы и выбираем первый (можно изменить логику)
        self.file_server.get_servers()
        self.file_server.select_first()

        table_name = self.dataset_model.raw_response.get("TableName")
        if not table_name:
            # Пробуем взять из кэша, полученного из каталога
            table_name = self._table_names_cache.get(dataset_id, "")
            if table_name:
                self.logger.info(f"TableName для справочника {dataset_id} взят из кэша каталога: {table_name}")
            else:
                self.logger.warning(f"TableName не найден для dataset_id={dataset_id} ни в описании, ни в каталоге")

        dataset_guid = self.dataset_model.raw_response.get("Guid", "")
        cache = {
            "dataset_model": self.dataset_model,
            "class_list": self.class_ctrl.classes_list,
            "file_server_id": self.file_server_model.id,
            "file_server_host": self.file_server_model.host,
            "file_server_port": self.file_server_model.port,
            "parameter_groups": self.dataset_model.parameter_group_collection,
            "dataset_guid": dataset_guid,
            "table_name": table_name,  # теперь содержит корректное имя или пустую строку
        }
        self._dataset_cache[dataset_id] = cache
        return cache

    def get_eri_datasets_list(self):
        self._ensure_authenticated()
        try:
            resp = self.http_client.get(DATASET_CATALOG_ENDPOINT)
            self._handle_response(resp)
            data = resp.json()
            folders = data.get("Collection", {}).get("_datasetCatalogFolderCollection", [])
            target_items = self._find_items_in_folder(folders, 58)
            datasets = []
            for item in target_items:
                ds_id = item.get("GroupId") or item.get("Id")
                ds_name = item.get("Caption") or f"Справочник {ds_id}"
                table_name = item.get("TableName") or ""  # <-- извлекаем TableName
                if ds_id and table_name:
                    self._table_names_cache[ds_id] = table_name  # сохраняем в кэш
                datasets.append({"id": ds_id, "name": ds_name})
            self.logger.info(f"Найдено справочников: {len(datasets)}")
            return datasets
        except Exception as e:
            self.logger.error(f"Ошибка получения справочников из каталога: {e}")
            return []

    def _find_items_in_folder(self, folders, target_id):
        """
        Рекурсивно ищет в списке папок папку с _guidKey.Id == target_id
        и возвращает все элементы (_datasetCatalogItems) из неё
        (включая элементы во вложенных папках).
        """
        for folder in folders:
            guid_key = folder.get("_guidKey", {})
            if guid_key.get("Id") == target_id:
                # Нашли нужную папку: собираем элементы из неё и всех подпапок
                items = list(folder.get("_datasetCatalogItems", []))
                sub_folders = folder.get("_datasetCatalogFolderCollection", [])
                for sub in sub_folders:
                    items.extend(self._flatten_folder(sub))
                return items
            # Рекурсивный спуск в подпапки
            sub_folders = folder.get("_datasetCatalogFolderCollection", [])
            result = self._find_items_in_folder(sub_folders, target_id)
            if result:
                return result
        return []

    def _flatten_folder(self, folder):
        """Рекурсивно собирает все элементы из папки и её дочерних папок."""
        items = list(folder.get("_datasetCatalogItems", []))
        for sub in folder.get("_datasetCatalogFolderCollection", []):
            items.extend(self._flatten_folder(sub))
        return items


    def get_eri_metadata(self, dataset_id: int) -> Dict[str, Any]:
        self._ensure_authenticated()
        cache = self._load_dataset_info(dataset_id)
        description = cache["dataset_model"].raw_response

        # --- 1. Сбор GUID параметров по Caption и Name ---
        param_guids = {}
        for group in description.get("ParameterGroupCollection", []):
            for param in group.get("Parameters", []):
                caption = param.get("Caption") or param.get("Name")
                guid_key = param.get("GuidKey") or {}
                guid = guid_key.get("Guid")
                if caption and guid:
                    param_guids[caption] = guid  # точное имя
                    param_guids[caption.strip().lower()] = guid  # нормализованное

        param_types = {}
        for group in description.get("ParameterGroupCollection", []):
            for param in group.get("Parameters", []):
                guid_key = param.get("GuidKey") or {}
                guid = guid_key.get("Guid")
                param_type = param.get("Type", 11)  # если тип не указан, считаем строкой
                if guid:
                    param_types[guid] = param_type

        self.logger.info(f"Первые 10 параметров: {list(param_guids.keys())[:10]}")

        # --- 2. Поиск основной группы (без связей) ---
        groups = description.get("ParameterGroupCollection", [])
        main_group_guid = ""
        for group in groups:
            guid_key = group.get("GuidKey") or {}
            guid = guid_key.get("Guid")
            if not guid:
                continue
            slave = group.get("SlaveGroupGuidKey")
            master = group.get("MasterGroupGuidKey")
            # Основная группа – та, у которой нет ни slave, ни master
            if (slave is None or not slave.get("Guid")) and (master is None or not master.get("Guid")):
                main_group_guid = guid
                self.logger.info(f"Основная группа: {group.get('Caption')} ({guid})")
                break

        if not main_group_guid and groups:
            # Fallback: первая группа с непустым GUID
            for group in groups:
                guid_key = group.get("GuidKey") or {}
                guid = guid_key.get("Guid")
                if guid:
                    main_group_guid = guid
                    self.logger.warning(
                        f"Основная группа не найдена, используется fallback-группа: {group.get('Caption')} ({guid})")
                    break

        print("\n=== ГРУППЫ ПАРАМЕТРОВ ===")
        for g in groups:
            guid_key = g.get("GuidKey") or {}
            guid = guid_key.get("Guid")
            caption = g.get("Caption")
            slave = g.get("SlaveGroupGuidKey")
            master = g.get("MasterGroupGuidKey")
            print(f"{caption} ({guid}) | slave={bool(slave)} master={bool(master)}")
        print("=== КОНЕЦ ГРУПП ===\n")

        # --- 3. Классы (уже исправлено ранее) ---
        raw_classes = cache.get("class_list", [])
        class_by_name = {}
        folder_class_id = 1
        folder_class_guid = ""

        for cls in raw_classes:
            cls_id = cls.get("id")
            cls_guid = cls.get("guid")
            cls_name = cls.get("name", "").strip()
            if not cls_id or int(cls_id) <= 0:
                continue
            if cls_name:
                class_by_name[cls_name.lower()] = {"id": cls_id, "guid": cls_guid}
                if "папка" in cls_name.lower():
                    folder_class_id = cls_id
                    folder_class_guid = cls_guid

        return {
            "param_guids": param_guids,
            "class_by_name": class_by_name,
            "main_group_guid": main_group_guid,
            "parameter_groups": cache["parameter_groups"],
            "dataset_id": dataset_id,
            "folder_class_id": folder_class_id,
            "folder_class_guid": folder_class_guid,
            "param_types": param_types,
        }

    def get_folder_info(self, dataset_id: int, folder_id: int) -> FolderModel:
        """Получает информацию о папке."""
        self._ensure_authenticated()
        self.folder.get_folder_info(dataset_id, folder_id)
        return self.folder_model

    # sarus_client/core/client.py (добавить в класс SarusClient)

    def create_eri_class(self, dataset_id: int, class_name: str, extensions=None):
        """
        Создаёт новый класс в справочнике ЭРИ.
        Возвращает dict {id, guid, name, extensions}.
        """
        self._ensure_authenticated()
        payload = {
            "DatasetID": dataset_id,
            "Name": class_name,
            "Extensions": extensions or []
        }
        # Используем существующий CLASSES_ENDPOINT = "/classes" (POST)
        response = self.http_client.post("/classes", json=payload)
        self._handle_response(response)
        data = response.json()
        new_id = data.get("Id")
        new_guid = data.get("Guid")
        if not new_id or not new_guid:
            raise ValueError("Не удалось получить ID/GUID созданного класса")
        self.logger.info(f"Создан новый класс '{class_name}' (ID={new_id})")
        return {
            "id": new_id,
            "guid": new_guid,
            "name": class_name,
            "extensions": extensions or []
        }

    def create_eri_parameter(self, dataset_id: int, param_name: str, param_type: int = 11) -> dict or None:
        self._ensure_authenticated()
        cache = self._load_dataset_info(dataset_id)
        table_name = cache.get("table_name", "")
        if not table_name:
            self.logger.warning(
                f"Невозможно создать параметр '{param_name}' – отсутствует TableName справочника {dataset_id}. Параметр будет пропущен.")
            return None

        payload = {
            "ParameterName": param_name,
            "Type": param_type,
            "ParameterGroupID": dataset_id,
            "ParameterGroupTableName": table_name,
            "ParameterComment": "",
            "ParameterTableName": "",
            "ParameterValue": "",
            "ParameterLength": 0,
            "ParameterFormat": 0,
            "ParameterListType": 0,
            "ParameterVisible": 1,
            "ParameterEditable": 1,
            "ParameterIndexed": 0,
            "ParameterRequired": 0,
            "ParameterNullable": 1,
            "TypeGroup": 0,
            "ParameterUserControl": "",
            "ParameterOldFieldName": "",
            "UnitGuid": "",
            "ParameterListValueCollection": []
        }

        try:
            response = self.http_client.post("/dataset/parameters", json=payload)
            self._handle_response(response)
            data = response.json()
            new_guid = data.get("Guid")
            if not new_guid:
                self.logger.error("Ответ не содержит Guid созданного параметра")
                return None
            self.logger.info(f"Параметр '{param_name}' создан (Guid={new_guid})")
            self._update_metadata_cache(dataset_id, param_name, new_guid, param_type)
            return {"guid": new_guid, "type": param_type}
        except Exception as e:
            self.logger.error(f"Не удалось создать параметр '{param_name}': {e}")
            return None

    def _update_metadata_cache(self, dataset_id, param_name, guid, ptype):
        """Вспомогательный метод: добавляет параметр в кэш метаданных."""
        if dataset_id in self._dataset_cache:
            meta = self._dataset_cache[dataset_id]
            if "param_guids" in meta:
                meta["param_guids"][param_name] = guid
                meta["param_guids"][param_name.strip().lower()] = guid
            if "param_types" in meta:
                meta["param_types"][guid] = ptype

    def upload_file(self, dataset_id: int, parent_id: int, file_path: str) -> int:
        """Загружает один файл и возвращает его ID. parent_id – ID папки в справочнике файлов."""
        self._ensure_authenticated()
        self._check_auth()
        cache = self._load_dataset_info(dataset_id)

        folder = self.get_folder_info(dataset_id, parent_id)
        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        file_class = self.class_ctrl.find_class_by_extension(ext)
        if not file_class:
            raise ValueError(f"No class for extension '{ext}'")
        self.object.create_file_object(
            dataset_id=dataset_id,
            folder_guid=folder.guid,
            folder_id=folder.id,
            class_guid=file_class["guid"],
            class_id=file_class["id"],
            file_name=os.path.basename(file_path),
            file_size_bytes=os.path.getsize(file_path),
            relative_path_folder=folder.relative_path,
            file_server_id=cache["file_server_id"],
            parameter_group_collection=cache["parameter_groups"]
        )
        self.token.get_token(
            object_id=self.object_model.object_id,
            file_path=file_path,
            file_server_host=cache["file_server_host"],
            file_server_port=cache["file_server_port"]
        )
        self.upload.upload_file(
            file_server_host=cache["file_server_host"],
            file_server_port=cache["file_server_port"],
            token=self.token_model.token,
            file_path=file_path
        )
        self.checkin.checkin(
            dataset_object_collection=self.object_model.full_response.get("DatasetObjectCollection"),
            parameter_group_collection=cache["parameter_groups"]
        )
        return self.object_model.object_id

    def upload_folder(self, dataset_id: int, parent_id: int, folder_path: str, create_subfolder: bool = True) -> bool:
        """Загружает папку рекурсивно."""
        self._ensure_authenticated()
        cache = self._load_dataset_info(dataset_id)

        # Получаем информацию о родительской папке
        parent_folder = self.get_folder_info(dataset_id, parent_id)

        folder_class = self.class_ctrl.get_folder_class()
        if not folder_class:
            raise ValueError("No suitable class for folders")

        folder_name = os.path.basename(folder_path)

        if create_subfolder:
            new_id, new_guid = self.folder_create.create_folder(
                dataset_id=dataset_id,
                parent_guid=parent_folder.guid,
                parent_id=parent_folder.id,
                class_guid=folder_class["guid"],
                class_id=folder_class["id"],
                folder_name=folder_name,
                relative_path=f"{parent_folder.relative_path}/{folder_name}" if parent_folder.relative_path else folder_name,
                parameter_group_collection=cache["parameter_groups"]
            )
            parent_id = new_id
            parent_guid = new_guid
            relative_base = folder_name
        else:
            parent_guid = parent_folder.guid
            relative_base = ""

        self._upload_folder_recursive(
            local_path=folder_path,
            parent_id=parent_id,
            parent_guid=parent_guid,
            relative_base=relative_base,
            folder_class=folder_class,
            dataset_id=dataset_id,
            cache=cache
        )
        return True

    def _upload_folder_recursive(self, local_path, parent_id, parent_guid, relative_base,
                                 folder_class, dataset_id, cache):
        for item in os.listdir(local_path):
            full_item = os.path.join(local_path, item)
            if os.path.isdir(full_item):
                new_relative = f"{relative_base}/{item}" if relative_base else item
                new_id, new_guid = self.folder_create.create_folder(
                    dataset_id=dataset_id,
                    parent_guid=parent_guid,
                    parent_id=parent_id,
                    class_guid=folder_class["guid"],
                    class_id=folder_class["id"],
                    folder_name=item,
                    relative_path=new_relative,
                    parameter_group_collection=cache["parameter_groups"]
                )
                self._upload_folder_recursive(
                    full_item, new_id, new_guid, new_relative,
                    folder_class, dataset_id, cache
                )
            else:
                self._upload_single_file(
                    file_path=full_item,
                    parent_id=parent_id,
                    parent_guid=parent_guid,
                    relative_base=relative_base,
                    dataset_id=dataset_id,
                    cache=cache
                )

    def _upload_single_file(self, file_path, parent_id, parent_guid, relative_base, dataset_id, cache):
        file_name = os.path.basename(file_path)
        ext = os.path.splitext(file_name)[1].lower().lstrip('.')
        file_class = self.class_ctrl.find_class_by_extension(ext)
        if not file_class:
            self.logger.warning(f"No class for {ext}, skipping {file_name}")
            return

        # Создаём объект
        self.object.create_file_object(
            dataset_id=dataset_id,
            folder_guid=parent_guid,
            folder_id=parent_id,
            class_guid=file_class["guid"],
            class_id=file_class["id"],
            file_name=file_name,
            file_size_bytes=os.path.getsize(file_path),
            relative_path_folder=relative_base,
            file_server_id=cache["file_server_id"],
            parameter_group_collection=cache["parameter_groups"]
        )

        # Токен
        self.token.get_token(
            object_id=self.object_model.object_id,
            file_path=file_path,
            file_server_host=cache["file_server_host"],
            file_server_port=cache["file_server_port"]
        )

        # Загрузка
        self.upload.upload_file(
            file_server_host=cache["file_server_host"],
            file_server_port=cache["file_server_port"],
            token=self.token_model.token,
            file_path=file_path
        )

        # Check-in
        self.checkin.checkin(
            dataset_object_collection=self.object_model.full_response.get("DatasetObjectCollection"),
            parameter_group_collection=cache["parameter_groups"]
        )
        self.logger.info(f"Uploaded: {file_name}")

    def link_objects(self, dataset1_id: int, object1_id: int, dataset2_id: int, object2_id: int) -> bool:
        """Создаёт связь между двумя объектами."""
        self._ensure_authenticated()
        cache = self._load_dataset_info(dataset1_id)  # достаточно одного справочника для получения метаданных связи
        # Находим информацию о связи в описании справочника
        link_info = self._find_link_info(self.dataset_model.raw_response)
        if not link_info:
            raise ValueError("Link information not found in dataset description")

        # Определяем, какой справочник slave, а какой master
        if link_info["is_slave_files"]:
            dataset_slave = dataset2_id
            object_slave = object2_id
            dataset_master = dataset1_id
            object_master = object1_id
        else:
            dataset_slave = dataset1_id
            object_slave = object1_id
            dataset_master = dataset2_id
            object_master = object2_id

        self.link.create_link(
            dataset_id_slave=dataset_slave,
            object_id_slave=object_slave,
            parent_id_master=object_master,
            table_name=link_info["table_name"]
        )
        self.logger.info(f"Link created: slave {dataset_slave}:{object_slave} -> master {object_master}")
        return True

    def _find_link_info(self, description: dict) -> dict:
        """Ищет связь со справочником файлов (ID=16) в описании справочника."""
        param_groups = description.get("ParameterGroupCollection", [])
        for group in param_groups:
            slave = group.get("SlaveGroupGuidKey")
            master = group.get("MasterGroupGuidKey")
            if slave and master:
                slave_id = slave.get("Id")
                master_id = master.get("Id")
                if slave_id == 16 or master_id == 16:
                    table_name = group.get("TableName", "")
                    is_slave_files = (slave_id == 16)
                    return {
                        "slave_id": slave_id,
                        "master_id": master_id,
                        "table_name": table_name,
                        "is_slave_files": is_slave_files
                    }
        return None

    # НОВЫЕ ФУНКЦИИ

    def _handle_response(self, response, expected_status=200):
        """Проверяет статус ответа и выбрасывает исключение при ошибке."""
        if response.status_code != expected_status:
            from utils.exceptions import APIError
            raise APIError(response.status_code, response.text)
        return response

    def _get_dataset_guid(self, dataset_id: int) -> str:
        """Возвращает GUID справочника по ID из кэша."""
        cache = self._dataset_cache.get(dataset_id)
        if cache and "dataset_guid" in cache:
            return cache["dataset_guid"]
        # Если нет в кэше, запросим описание
        desc = self.dataset.get_description(dataset_id)
        # Извлекаем GUID из ответа (обычно в корне или в GroupGuidKey)
        return desc.get("Guid", "")

    def _get_class_guid(self, dataset_id: int, class_id: int) -> str:
        """Возвращает GUID класса по ID из списка классов справочника."""
        cache = self._load_dataset_info(dataset_id)
        classes = cache.get("class_list", [])
        for cls in classes:
            if cls.get("id") == class_id:
                return cls.get("guid", "")
        return ""

    def _get_parent_guid(self, dataset_id: int, parent_id: int) -> str:
        """Возвращает GUID родительского объекта. Если parent_id == 0, возвращает пустую строку."""
        if parent_id == 0:
            return ""
        folder_info = self.get_folder_info(dataset_id, parent_id)
        return folder_info.guid

    def create_eri_object(self, dataset_id: int, parent_id: int, class_id: int,
                          attributes: Dict[str, Any], param_guids: Dict[str, str],
                          main_group_guid: str, parameter_groups: list,
                          dataset_guid: str = None, class_guid: str = None, parent_guid: str = None,
                          param_types: dict = None) -> int:
        self._ensure_authenticated()
        self._check_auth()

        # Если GUID не переданы, пытаемся извлечь из кэша метаданных
        if dataset_guid is None:
            dataset_guid = self._get_dataset_guid(dataset_id)
        if class_guid is None:
            class_guid = self._get_class_guid(dataset_id, class_id)
        if parent_guid is None:
            parent_guid = self._get_parent_guid(dataset_id, parent_id)

        params_list = []
        for guid, value in attributes.items():
            if param_types:
                param_type = param_types.get(guid, 11)  # из метаданных, по умолчанию строка
            else:
                param_type = 11 if isinstance(value, str) else 2
            params_list.append({
                "AdditionalGroupGuid": "",
                "AdditionalGuids": [],
                "GroupGuid": main_group_guid,  # или конкретная группа параметра
                "Guid": guid,
                "IsModified": False,
                "IsNull": False,
                "Type": param_type,
                "Value": str(value)
            })

        payload = {
            "CreateWithRegularState": False,
            "GuidNearObject": "",
            "ParameterGroupCollection": parameter_groups,
            "DatasetObjectCollection": [{
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
                    "Guid": dataset_guid,
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
                "Parameters": {"Parameters": params_list},
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
            }]
        }

        response = self.http_client.post("/objects", json=payload)
        self._handle_response(response)
        data = response.json()
        obj = data["DatasetObjectCollection"][0]
        return obj["GuidKey"]["Id"]

    def create_document(self, dataset_id: int, parent_id: int, file_name: str, file_path: str) -> int:
        """
        Создаёт объект документа в справочнике 'Документы' и загружает файл НД.
        Возвращает ID созданного документа.
        """
        # Загружаем файл PDF как обычный файл
        file_id = self.upload_file(dataset_id=16, parent_id=parent_id, file_path=file_path)

        # ID класса "Документ" – нужно уточнить в модели данных САРУС
        doc_class_id = 200  # Замените на реальный ID
        doc_class_guid = "..."  # Замените на реальный GUID

        # Создаём объект документа
        doc_attributes = {"Name": file_name}
        doc_id = self.create_eri_object(dataset_id, parent_id, doc_class_id, doc_attributes,
                                        self.get_eri_metadata(dataset_id)["param_guids"],
                                        self.get_eri_metadata(dataset_id)["main_group_guid"])
        # Связываем документ с файлом
        self.link_objects(dataset_id, doc_id, 16, file_id)
        return doc_id

    def link_eri_to_file(self, eri_dataset_id: int, eri_object_id: int, file_object_id: int):
        """Связь ЭРИ с файлом (3D-моделью). Ошибки логируются, но не прерывают процесс."""
        try:
            self.link.create_link(
                dataset_id_slave=16,  # справочник файлов
                object_id_slave=file_object_id,
                parent_id_master=eri_object_id,
                table_name="Link_eri_files"  # замените на реальное имя таблицы связи при необходимости
            )
        except Exception as e:
            self.logger.error(f"Не удалось создать связь ЭРИ-файл: {e}")

    def link_eri_to_document(self, eri_dataset_id: int, eri_object_id: int, doc_object_id: int):
        """Связь ЭРИ с документом. Ошибки логируются, но не прерывают процесс."""
        try:
            # Пытаемся найти таблицу связи; если не найдена – пропускаем
            cache = self._load_dataset_info(eri_dataset_id)
            description = cache["dataset_model"].raw_response
            link_info = self._find_link_info_for_dataset(description, target_dataset_id=eri_dataset_id)
            if not link_info:
                self.logger.warning("Не найдена таблица связи с документами, связь не создана")
                return
            if link_info["slave_id"] == eri_dataset_id:
                dataset_slave = eri_dataset_id
                object_slave = eri_object_id
                parent_master = doc_object_id
            else:
                dataset_slave = link_info["slave_id"]
                object_slave = doc_object_id
                parent_master = eri_object_id
            self.link.create_link(
                dataset_id_slave=dataset_slave,
                object_id_slave=object_slave,
                parent_id_master=parent_master,
                table_name=link_info["table_name"]
            )
        except Exception as e:
            self.logger.error(f"Не удалось создать связь ЭРИ-документ: {e}")

    def add_3d_model_to_eri(self, eri_dataset_id: int, eri_object_id: int, model_file_id: int):
        """
        Добавляет запись в список объектов 3D справочника ЭРИ.
        Это специальная связь, реализуемая через параметр-список объектов.
        """
        # Для этого нужно обновить параметр "Список 3D моделей" у объекта ЭРИ
        # Пока упрощённо: используем обычную связь
        self.link_eri_to_file(eri_dataset_id, eri_object_id, model_file_id)

    def _ensure_session_alive(self) -> bool:
        """
        Проверяет, что текущая сессия активна. Если нет – переавторизуется.
        Возвращает True, если сессия жива или успешно восстановлена.
        """
        if not self._is_authenticated:
            return False

        # Лёгкий запрос, требующий только аутентификации (без мандатного доступа)
        # Например, получение списка справочников (не требует ID)
        try:
            response = self.http_client.get("/dataset/catalog")
            if response.status_code == 200:
                return True
            self.logger.warning(f"Сессия недействительна (код {response.status_code})")
        except Exception as e:
            self.logger.warning(f"Ошибка при проверке сессии: {e}")

        # Пытаемся переавторизоваться
        self.logger.info("Попытка повторной аутентификации...")
        try:
            self.authenticate()  # использует сохранённые или переданные ранее креды
            return True
        except Exception as e:
            self.logger.error(f"Не удалось восстановить сессию: {e}")
            self._is_authenticated = False
            raise RuntimeError("Сессия недействительна и не может быть восстановлена") from e

    def _check_auth(self):
        """Проверяет аутентификацию и живость сессии."""
        self._ensure_authenticated()
        if not self._ensure_session_alive():
            raise RuntimeError("Не удалось подтвердить активную сессию")

    def create_eri_folder(self, dataset_id: int, parent_id: int, parent_guid: str,
                          folder_name: str, folder_class_id: int, folder_class_guid: str,
                          parameter_groups: list) -> Tuple[int, str]:
        """
        Создаёт папку в справочнике ЭРИ и возвращает (ID, GUID).
        """
        self._ensure_authenticated()
        relative_path = folder_name  # или строить полный путь
        return self.folder_create.create_folder(
            dataset_id=dataset_id,
            parent_guid=parent_guid,
            parent_id=parent_id,
            class_guid=folder_class_guid,
            class_id=folder_class_id,
            folder_name=folder_name,
            relative_path=relative_path,
            parameter_group_collection=parameter_groups
        )

    def _find_link_info_for_dataset(self, description: dict, target_dataset_id: int) -> dict:
        """Ищет связь, в которой участвует target_dataset_id."""
        param_groups = description.get("ParameterGroupCollection", [])
        for group in param_groups:
            slave = group.get("SlaveGroupGuidKey")
            master = group.get("MasterGroupGuidKey")
            if slave and master:
                slave_id = slave.get("Id")
                master_id = master.get("Id")
                if slave_id == target_dataset_id or master_id == target_dataset_id:
                    return {
                        "slave_id": slave_id,
                        "master_id": master_id,
                        "table_name": group.get("TableName", ""),
                    }
        return None

    def get_documents_metadata(self) -> Dict[str, Any]:
        """Загружает метаданные справочника документов (один раз)."""
        if not hasattr(self, '_documents_metadata'):
            doc_dataset_id = default_config.documents_dataset_id
            # Загружаем описание справочника
            self.dataset.get_description(doc_dataset_id)
            desc = self.dataset_model.raw_response
            # Собираем GUID параметров
            param_guids = {}
            param_types = {}
            for group in desc.get("ParameterGroupCollection", []):
                for param in group.get("Parameters", []):
                    caption = param.get("Caption") or param.get("Name")
                    guid_key = param.get("GuidKey") or {}
                    guid = guid_key.get("Guid")
                    if caption and guid:
                        param_guids[caption] = guid
                        param_guids[caption.strip().lower()] = guid
                    if guid:
                        param_types[guid] = param.get("Type", 11)
            # Основная группа параметров
            main_group_guid = ""
            for group in desc.get("ParameterGroupCollection", []):
                guid_key = group.get("GuidKey") or {}
                guid = guid_key.get("Guid")
                slave = group.get("SlaveGroupGuidKey")
                master = group.get("MasterGroupGuidKey")
                if (slave is None or not slave.get("Guid")) and (master is None or not master.get("Guid")):
                    main_group_guid = guid
                    break
            if not main_group_guid and desc.get("ParameterGroupCollection"):
                main_group_guid = desc["ParameterGroupCollection"][0].get("GuidKey", {}).get("Guid", "")
            self._documents_metadata = {
                "dataset_id": doc_dataset_id,
                "param_guids": param_guids,
                "param_types": param_types,
                "main_group_guid": main_group_guid,
                "parameter_groups": self.dataset_model.parameter_group_collection,
            }
        return self._documents_metadata

    def ensure_file_folder(self, folder_name: str) -> int:
        """
        Создаёт или возвращает ID папки в корне справочника файлов (ID=16).
        После создания выполняет check‑in, чтобы папка не оставалась в режиме редактирования.
        """
        if not hasattr(self, '_file_folder_cache'):
            self._file_folder_cache = {}
        if folder_name in self._file_folder_cache:
            return self._file_folder_cache[folder_name]

        dataset_id_files = default_config.files_dataset_id  # 16
        root_parent_id = default_config.files_root_parent_id  # 16 (корень)

        # Загружаем классы справочника файлов, чтобы найти класс "Папка"
        self.class_ctrl.get_classes(dataset_id_files)
        folder_class = self.class_ctrl.get_folder_class()
        if not folder_class:
            raise RuntimeError("Не удалось найти класс 'Папка' в справочнике файлов")

        # Пытаемся найти существующую папку с таким именем в корне
        existing_id = self._find_folder_by_name(dataset_id_files, root_parent_id, folder_name)
        if existing_id:
            self._file_folder_cache[folder_name] = existing_id
            return existing_id

        # Информация о корневой папке (корень – сам справочник)
        root_info = self.get_folder_info(dataset_id_files, root_parent_id)
        root_guid = root_info.guid

        # Создаём папку
        new_id, new_guid = self.folder_create.create_folder(
            dataset_id=dataset_id_files,
            parent_guid=root_guid,
            parent_id=root_parent_id,
            class_guid=folder_class["guid"],
            class_id=folder_class["id"],
            folder_name=folder_name,
            relative_path=folder_name,
            parameter_group_collection=self._load_dataset_info(dataset_id_files)["parameter_groups"]
        )

        # Check‑in, чтобы папка не висела в режиме редактирования
        self._checkin_folder(dataset_id_files, new_id)
        self._file_folder_cache[folder_name] = new_id
        self.logger.info(f"Создана и подтверждена папка {folder_name} (ID={new_id}) в справочнике файлов")
        return new_id

    def _find_folder_by_name(self, dataset_id: int, parent_id: int, folder_name: str) -> Optional[int]:
        """Ищет папку по имени в указанной родительской папке, используя POST /objects."""
        payload = {
            "GroupId": dataset_id,
            "ParentId": parent_id,
            "Versions": False,
            "PrototypesMode": False,
            "WithLinkedObjects": False,
            "LoadAnyReferenceLinkObjects": False,
            "LimitCountObjects": 1000,  # увеличиваем лимит
            "ParameterGroupCollection": []
        }
        try:
            response = self.http_client.post("/objects", json=payload)
            if response.status_code != 200:
                return None
            data = response.json()
            collection = data.get("DatasetObjectCollection", [])
            for obj in collection:
                # Проверяем, что это папка (класс = класс папки)
                class_key = obj.get("ClassGuidKey", {})
                # Если не знаем ID класса папки, ищем по имени параметра
                params = obj.get("Parameters", {}).get("Parameters", [])
                for p in params:
                    if p.get("Guid") == PARAM_NAME_GUID and p.get("Value") == folder_name:
                        # Дополнительно проверяем, что это папка (можно по наличию расширений или классу)
                        guid_key = obj.get("GuidKey", {})
                        return guid_key.get("Id")
            return None
        except Exception as e:
            self.logger.warning(f"Error searching for folder: {e}")
            return None

    def _checkin_folder(self, dataset_id: int, folder_id: int):
        """Подтверждает создание папки, используя существующий метод checkin."""
        # Получаем полную информацию о папке
        folder_info = self.get_folder_info(dataset_id, folder_id)
        # Формируем DatasetObjectCollection из полученных данных
        # Для check-in нужен объект с теми же полями, что и при создании, но можно использовать упрощённый вариант
        # Согласно документации САРУС, достаточно передать объект с GuidKey, GroupGuidKey, ParentGuidKey, ClassGuidKey и Parameters.
        obj = {
            "GuidKey": {"Id": folder_id, "Guid": folder_info.guid},
            "GroupGuidKey": {"Id": dataset_id, "Guid": ""},  # GUID справочника можно получить
            "ParentGuidKey": {"Id": folder_info.id, "Guid": folder_info.guid},  # Здесь может быть родитель
            "ClassGuidKey": {"Id": 0, "Guid": ""},  # Не обязательно
            "Parameters": {"Parameters": []}
        }
        # Используем контроллер checkin
        self.checkin.checkin(
            dataset_object_collection=[obj],
            parameter_group_collection=self._load_dataset_info(dataset_id)["parameter_groups"]
        )
        self.logger.info(f"Check-in выполнен для папки {folder_id}")
