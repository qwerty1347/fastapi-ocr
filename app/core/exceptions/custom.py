class BusinessException(Exception):
    def __init__(self, code: int, message: str, errors: list | None = None):
        self.code = code
        self.message = message
        self.errors = errors