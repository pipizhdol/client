# sarus_client/utils/exceptions.py

class SarusError(Exception):
    """Базовое исключение для всех ошибок клиента."""
    pass


class AuthError(SarusError):
    """Ошибка авторизации."""
    pass


class APIError(SarusError):
    """Ошибка при выполнении запроса к API."""

    def __init__(self, status_code: int, response_text: str):
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(f"API error {status_code}: {response_text}")


class ValidationError(SarusError):
    """Ошибка валидации входных данных."""
    pass


class NotFoundError(SarusError):
    """Объект не найден."""
    pass
