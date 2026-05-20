# sarus_client/core/eri_importer.py
import os
import shutil
import tempfile
import re
from decimal import Decimal
from typing import Dict, Optional, Any
from config import default_config
from mdb_reader import read_table_data
from parsers.pcblib_parser import extract_model_names_from_pcblib

"""
FIELD_TO_PARAM = {
    'NameСomp': 'Name',
    'BaseDoccomp': 'Designation',
    'Mass': 'Mass',
    'TypeComp': 'Type',
    'Value': 'Value',
    'Tolerance': 'Tolerance',
    'Manufacturer': 'Manufacturer',
    'OperTemperRange': 'OperTemperRange',
    'ClimaticVersion': 'ClimaticVersion',
    'PackageReference': 'PackageReference',
    'Power': 'Power',
    'Voltage': 'Voltage',
    'Code': 'Code',
}
"""


class EriImporter:
    """
    Импортёр данных из справочника ЭРИ ВНИИЭФ в САРУС.
    Реализует логику согласно концепции интеграции.
    """

    def __init__(self, client, eri_dataset_id: int, eri_dataset_name: str, eri_metadata: Dict[str, Any], log_callback=None):
        self.client = client
        self.eri_dataset_id = eri_dataset_id
        self.eri_dataset_name = eri_dataset_name
        self.eri_metadata = eri_metadata
        self.log = log_callback or print
        self.temp_dir = tempfile.mkdtemp(prefix="eri_import_")
        self.folder_cache = {}
        self.file_folder_id = None          # ID папки в справочнике файлов
        self.doc_metadata = None            # метаданные справочника документов

    def __del__(self):
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _convert_value(self, value, target_type: int):
        """Форматирует значение под ожидаемый тип параметра САРУС."""
        from datetime import datetime, date

        # Дата и время -> "ДД.ММ.ГГГГ"
        if isinstance(value, (datetime, date)):
            return value.strftime("%d.%m.%Y")

        # Для числовых типов (2-целое, 6-вещественное, 7-целое большое) —
        # гарантируем точку в качестве десятичного разделителя
        if target_type in (2, 6, 7) and isinstance(value, (float, int, Decimal)):
            return str(value)  # Decimal и float уже с точкой

        # Остальное (строки, None) возвращаем как строку
        return str(value) if value is not None else ""

    def _ensure_file_folder(self):
        """Создаёт или получает ID папки в справочнике файлов с именем справочника ЭРИ."""
        if self.file_folder_id is None:
            self.file_folder_id = self.client.ensure_file_folder(self.eri_dataset_name)
        return self.file_folder_id

    def _ensure_doc_metadata(self):
        if self.doc_metadata is None:
            self.doc_metadata = self.client.get_documents_metadata()
        return self.doc_metadata

    def import_from_mdb(self, mdb_path, table_name, base_path,
                        create_missing_classes=False, create_missing_params=False, stop_event=None):
        # Создаём подпапку в справочнике файлов один раз
        self._ensure_file_folder()
        self._import_table(mdb_path, table_name, base_path,
                           create_missing_classes, create_missing_params, stop_event)

    def _import_table(self, mdb_path, table_name, base_path,
                      create_missing_classes, create_missing_params, stop_event):
        columns, rows = read_table_data(mdb_path, table_name)
        self.log(f"Прочитано {len(rows)} записей")

        # Определяем или создаём папку для типа ЭРИ в справочнике
        folder_id = self._get_or_create_eri_folder(table_name)

        for idx, row in enumerate(rows):
            # Проверка флага остановки
            if stop_event and stop_event.is_set():
                self.log("Импорт прерван пользователем")
                break

            record = dict(zip(columns, row))
            part_number = record.get('Part Number', '')
            self.log(f"\n[{idx + 1}/{len(rows)}] {part_number}")
            try:
                self._process_record(record, base_path, folder_id,
                                     create_missing_classes, create_missing_params)
            except Exception as e:
                self.log(f"  ОШИБКА: {e}")

        if stop_event and stop_event.is_set():
            self.log("Импорт остановлен. Обработано не всё.")

    def _process_record(self, record: Dict, base_path: str, parent_folder_id: int,
                        create_missing_classes: bool, create_missing_params: bool):
        # 1. Создать объект ЭРИ
        eri_object_id = self._create_eri_object(record, parent_folder_id,
                                                create_missing_classes, create_missing_params)

        if not eri_object_id:
            self.log("  Не удалось создать объект ЭРИ, пропуск")
            return

        # 2. Обработать 3D-модели (.stp)
        for i in range(1, 10):  # предположим, не более 9 моделей
            footprint_key = f'Footprint Path' if i == 1 else f'Footprint Path{i}'
            footprint_path = record.get(footprint_key, '')
            if not footprint_path:
                break
            self._process_3d_models(footprint_path, base_path, record, eri_object_id)

        # 3. Обработать НД (PDF)
        for i in range(1, 10):
            url_key = f'ComponentLink{i}URL'
            desc_key = f'ComponentLink{i}Description'
            nd_url = record.get(url_key, '')
            if not nd_url:
                break
            nd_desc = record.get(desc_key, '')
            self._process_nd(nd_url, nd_desc, base_path, eri_object_id)

        # 4. Загружаем пустую RGP-модель с именем = Part Number
        part_number = record.get('Part Number', '')
        rgp_file_id = self._copy_empty_rgp_model(part_number)
        if rgp_file_id:
            self.client.add_3d_model_to_eri(self.eri_dataset_id, eri_object_id, rgp_file_id)
            self.log("  Привязана именованная RGP-модель")
        else:
            self.log("  Предупреждение: не удалось создать RGP-модель")


    def _create_eri_object(self, record: Dict, parent_folder_id: int,
                           create_missing_classes: bool = False,
                           create_missing_params: bool = False) -> Optional[int]:

        # --- маппинг типов для улучшения поиска класса ---
        type_mapping = {
            'конденсатор': 'конденсаторы',
            'резистор': 'резисторы',
            'микросхема': 'микросхемы',
            'транзистор': 'транзисторы',
            'диод': 'диоды',
            'катушка': 'катушки',
            'разъем': 'разъемы',
            'переключатель': 'переключатели',
            'предохранитель': 'предохранители',
            'блок': 'блоки',
        }

        type_comp = record.get('TypeComp', '').strip()
        self.log(f"  Тип изделия (TypeComp): '{type_comp}'")

        class_by_name = self.eri_metadata.get("class_by_name", {})
        folder_class_id = self.eri_metadata.get("folder_class_id", 1)

        if not class_by_name:
            self.log("  ОШИБКА: словарь классов пуст!")
            return None

        type_lower = type_comp.lower()
        search_type = type_mapping.get(type_lower, type_lower)

        class_id = None

        # 1. Поиск по преобразованному типу
        for cls_name, cls_info in class_by_name.items():
            if search_type in cls_name or cls_name in search_type:
                class_id = cls_info["id"]
                self.log(f"  Найден класс '{cls_name}' (ID={class_id}) по типу '{type_comp}'")
                break

        # Если класс не найден
        if not class_id:
            if create_missing_classes:
                # Попытка создать новый класс под тип изделия
                try:
                    new_class = self.client.create_eri_class(
                        dataset_id=self.eri_dataset_id,
                        class_name=type_comp  # используем исходное значение TypeComp
                    )
                    # Добавляем в кэш метаданных
                    self.eri_metadata["class_by_name"][type_comp.lower()] = {
                        "id": new_class["id"],
                        "guid": new_class["guid"]
                    }
                    class_id = new_class["id"]
                    self.log(f"  Создан новый класс '{type_comp}' (ID={class_id})")
                except Exception as e:
                    self.log(f"  Не удалось создать класс '{type_comp}': {e}")
                    return None  # пропускаем запись
            else:
                # Fallback – первый не-папка (старое поведение)
                for cls_name, cls_info in class_by_name.items():
                    if cls_info["id"] != folder_class_id:
                        class_id = cls_info["id"]
                        self.log(f"  Использован fallback-класс '{cls_name}' (ID={class_id})")
                        break

        # Если после всех попыток class_id отсутствует, пропускаем
        if not class_id:
            self.log("  Не удалось определить класс ЭРИ")
            return None

        param_guids = self.eri_metadata.get("param_guids", {})
        param_types = self.eri_metadata.get("param_types", {})  # <-- получаем типы
        main_group_guid = self.eri_metadata.get("main_group_guid")
        if not main_group_guid:
            self.log("  Не найден GUID основной группы параметров")
            return None
        self.log(f"  Используется основная группа с GUID: {main_group_guid}")

        # --- Прямое сопоставление полей с GUID параметров ---
        attributes = {}  # <-- ИНИЦИАЛИЗАЦИЯ ЗДЕСЬ
        skipped = []  # <-- ИНИЦИАЛИЗАЦИЯ ЗДЕСЬ
        for field, value in record.items():
            if value is None or value == '':
                continue
            guid = param_guids.get(field) or param_guids.get(field.strip().lower())
            if guid:
                target_type = param_types.get(guid, 11)
                value = self._convert_value(value, target_type)
                attributes[guid] = value
            else:
                # Пытаемся создать параметр, если разрешено
                if create_missing_params:
                    # Определяем тип: если значение похоже на число, то 6 (вещественное), иначе 11 (строка)
                    try:
                        float(str(value).replace(',', '.'))
                        ptype = 6
                    except ValueError:
                        ptype = 11
                    new_param = self.client.create_eri_parameter(
                        dataset_id=self.eri_dataset_id,
                        param_name=field,
                        param_type=ptype
                    )
                    if new_param:
                        guid = new_param["guid"]
                        ptype = new_param["type"]
                        # Обновляем локальные справочники
                        param_guids[field] = guid
                        param_guids[field.strip().lower()] = guid
                        param_types[guid] = ptype
                        converted = self._convert_value(value, ptype)
                        attributes[guid] = converted
                        self.log(f"  Создан параметр '{field}' (GUID={guid})")
                    else:
                        skipped.append(field)
                else:
                    skipped.append(field)

        self.log(f"  Найдено {len(attributes)} атрибутов для передачи")
        if skipped:
            self.log(f"  Пропущено полей (не найден GUID): {skipped[:5]}...")

        try:
            obj_id = self.client.create_eri_object(
                dataset_id=self.eri_dataset_id,
                parent_id=parent_folder_id,
                class_id=class_id,
                attributes=attributes,
                param_guids=param_guids,
                main_group_guid=main_group_guid,
                parameter_groups=self.eri_metadata["parameter_groups"],
                param_types=param_types  # передаём типы
            )
            self.log(f"  Создан объект ЭРИ ID={obj_id} (класс {class_id}) с {len(attributes)} атрибутами")
            return obj_id
        except Exception as e:
            self.log(f"  Ошибка создания объекта ЭРИ: {e}")
            return None

    def _process_3d_models(self, footprint_path: str, base_path: str,
                           record: Dict, eri_object_id: int):
        pcblib_full = self._resolve_relative_path(footprint_path, base_path)
        if not os.path.exists(pcblib_full):
            self.log(f"  Файл .pcblib не найден: {pcblib_full}")
            return
        model_names = extract_model_names_from_pcblib(pcblib_full)
        for model_name in model_names:
            model_path = self._locate_model_file(model_name, base_path, record)
            if model_path and os.path.exists(model_path):
                local_copy = os.path.join(self.temp_dir, model_name)
                shutil.copy2(model_path, local_copy)
                # Загружаем в подпапку справочника файлов
                file_id = self.client.upload_file(default_config.files_dataset_id,
                                                  self._ensure_file_folder(), local_copy)
                self.client.link_eri_to_file(self.eri_dataset_id, eri_object_id, file_id)
                self.log(f"  Привязана 3D-модель: {model_name}")
            else:
                self.log(f"  3D-модель не найдена: {model_name}")

    def _process_nd(self, nd_url: str, nd_desc: str, base_path: str, eri_object_id: int):
        nd_path = self._resolve_nd_path(nd_url, base_path)
        if not nd_path or not os.path.exists(nd_path):
            self.log(f"  НД не найден: {nd_url}")
            return

        # 1. Загружаем PDF как файл в подпапку справочника файлов
        local_copy = os.path.join(self.temp_dir, os.path.basename(nd_path))
        shutil.copy2(nd_path, local_copy)
        file_id = self.client.upload_file(default_config.files_dataset_id,
                                          self._ensure_file_folder(), local_copy)
        self.log(f"  Файл НД загружен (ID={file_id})")

        # 2. Создаём объект документа в справочнике документов (ID=701) в папке 2
        doc_meta = self._ensure_doc_metadata()
        doc_dataset_id = default_config.documents_dataset_id       # 701
        doc_parent_id = default_config.documents_target_folder_id # 2
        doc_name = os.path.basename(nd_path)

        # Находим GUID параметра "Наименование" (или "Name")
        name_guid = (doc_meta["param_guids"].get("Name") or
                     doc_meta["param_guids"].get("Наименование"))
        attributes = {}
        if name_guid:
            attributes[name_guid] = doc_name
        # Можно добавить описание из nd_desc
        desc_guid = doc_meta["param_guids"].get("Description") or doc_meta["param_guids"].get("Описание")
        if desc_guid and nd_desc:
            attributes[desc_guid] = nd_desc

        doc_id = self.client.create_eri_object(
            dataset_id=doc_dataset_id,
            parent_id=doc_parent_id,          # папка 2
            class_id=1,                       # ID класса "Документ" – уточнить при необходимости
            attributes=attributes,
            param_guids=doc_meta["param_guids"],
            main_group_guid=doc_meta["main_group_guid"],
            parameter_groups=doc_meta["parameter_groups"],
            param_types=doc_meta["param_types"]
        )
        self.log(f"  Создан объект документа ID={doc_id}")

        # 3. Связываем файл и документ
        self.client.link_objects(doc_dataset_id, doc_id,
                                 default_config.files_dataset_id, file_id)
        # 4. Связываем документ с объектом ЭРИ
        self.client.link_eri_to_document(self.eri_dataset_id, eri_object_id, doc_id)
        self.log(f"  Документ {doc_id} привязан к ЭРИ {eri_object_id}")

    def _get_eri_class_id(self, record: Dict) -> int:
        """
        Возвращает ID класса объекта в справочнике ЭРИ.
        Пока упрощённо: всегда возвращаем ID базового типа ЭРИ.
        В дальнейшем можно выбирать по типу изделия.
        """
        # Замените на реальный ID класса из модели данных САРУС
        return 100  # пример

    def _resolve_relative_path(self, rel_path: str, base_path: str) -> str:
        """Преобразует относительный путь из .mdb в абсолютный."""
        # Удаляем возможные '..\\..\\' и объединяем с base_path
        rel_path = rel_path.replace('..\\', '').replace('../', '')
        return os.path.normpath(os.path.join(base_path, rel_path))

    def _locate_model_file(self, model_name: str, base_path: str, record: Dict) -> Optional[str]:
        """
        Находит файл 3D-модели по имени.
        Ищет в каталоге Kompas/<тип ЭРИ>/.
        """
        # Определяем тип ЭРИ (каталог 2 уровня) из названия таблицы или поля
        # Пока ищем просто в Kompas
        kompas_dir = os.path.join(base_path, 'Kompas')
        for root, dirs, files in os.walk(kompas_dir):
            if model_name in files:
                return os.path.join(root, model_name)
        return None

    def _resolve_nd_path(self, nd_url: str, base_path: str) -> Optional[str]:
        """
        Преобразует ссылку на НД в абсолютный путь.
        nd_url обычно имеет вид: \\\\base-s-fs-04\\NKBS\\...\\file.pdf
        Если это сетевой путь, он должен быть доступен.
        """
        # Если путь сетевой, оставляем как есть
        if nd_url.startswith('\\\\'):
            return nd_url
        # Иначе пытаемся собрать относительно base_path
        return os.path.normpath(os.path.join(base_path, nd_url))

    def _copy_empty_rgp_model(self, part_number: str) -> Optional[int]:
        """
        Копирует шаблонную RGP-модель, переименовывает в {part_number}.RGP,
        загружает в созданную папку справочника файлов и возвращает ID файла.
        """
        possible_paths = [
            r"C:\Program Files\RPLM\RPLM 2025.2.1.8-VNF\Prototypes\Модель.RGP",
            r"C:\Program Files\RPLM\RPLM\Prototypes\Модель.RGP",
        ]
        for src in possible_paths:
            if os.path.exists(src):
                # Формируем имя файла: part_number.RGP (заменяем недопустимые символы)
                safe_name = re.sub(r'[\\/*?:"<>|]', '_', str(part_number))
                dest_name = f"{safe_name}.RGP"
                dest = os.path.join(self.temp_dir, dest_name)
                shutil.copy2(src, dest)
                # Загружаем в подпапку справочника файлов
                file_id = self.client.upload_file(default_config.files_dataset_id,
                                                  self._ensure_file_folder(), dest)
                self.log(f"  Загружена RGP-модель как {dest_name} (ID={file_id})")
                return file_id
        self.log("  Не найден файл пустой модели RGP")
        return None

    def _parse_mass(self, mass_str):
        """Извлекает числовое значение массы из строки вида '50 г'."""
        if not mass_str:
            return 0.0
        import re
        match = re.search(r'(\d+[.,]?\d*)', str(mass_str))
        if match:
            return float(match.group(1).replace(',', '.'))
        return 0.0

    def _get_or_create_eri_folder(self, table_name: str) -> int:
        self.log(f"  (Используется корень справочника для '{table_name}')")
        return 0
