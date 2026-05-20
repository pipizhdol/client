# sarus_client/utils/constants.py

"""
Константы API и GUID параметров.
"""

# Эндпоинты (URI)
AUTH_ENDPOINT = "/user/auth"
ACCESS_LEVELS_SESSION_ENDPOINT = "/access/levels/session"
DATASET_DESCRIPTION_ENDPOINT = "/dataset/description"
OBJECTS_ENDPOINT = "/objects/none"
FILE_SERVERS_ENDPOINT = "/files/servers?fit=true"
CLASSES_ENDPOINT = "/classes"
OBJECTS_CREATE_ENDPOINT = "/objects"
TOKEN_ENDPOINT = "/files/token"
CHECKIN_ENDPOINT = "/objects/edit/checkin"
LINK_ENDPOINT = "/objects/link"
DATASET_CATALOG_ENDPOINT = "/dataset/catalog"

# GUID параметров объектов (справочников)
# Наименование объекта
PARAM_NAME_GUID = "63aa0058-4a37-4754-8973-ffbc1b88f576"
# Относительный путь
PARAM_PATH_GUID = "adda774c-dbdf-48ba-bcf6-87bb42a67e90"
# Размер файла (байты)
PARAM_SIZE_GUID = "1cc37816-33dc-4de4-bcfd-645041795012"
# Идентификатор файлового сервера
PARAM_SERVER_GUID = "d7e01480-b2c9-445d-886b-7582435a5dba"
