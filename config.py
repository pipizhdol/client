# sarus_client/config.py

from dataclasses import dataclass


@dataclass
class SarusConfig:
    """Конфигурация подключения к САРУС."""
    base_url: str = "http://127.0.0.1:35000/v1"
    login: str = "Администратор"
    password: str = "d41d8cd98f00b204e9800998ecf8427e"
    documents_dataset_id: int = 701  # Справочник "Документы"
    documents_target_folder_id: int = 2  # Папка внутри справочника документов
    files_dataset_id: int = 16  # Справочник "Файлы"
    files_root_parent_id: int = 16  # Корень справочника файлов 
    # можно добавить другие параметры: timeout, retries и т.д.


# Создаём глобальный объект конфигурации (потом можно будет менять)
default_config = SarusConfig()
