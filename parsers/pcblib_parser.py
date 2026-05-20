# sarus_client/parsers/pcblib_parser.py

import re


def extract_model_names_from_pcblib(pcblib_path: str):
    """Извлекает имена 3D-моделей (STP) из файла .pcblib."""
    models = []
    try:
        with open(pcblib_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Ищем строки вида MODEL.NAME=имя_файла.stp
            matches = re.findall(r'MODEL\.NAME=([^\s]+\.stp)', content, re.IGNORECASE)
            models = list(set(matches))
    except Exception as e:
        print(f"Ошибка чтения .pcblib: {e}")
    return models
