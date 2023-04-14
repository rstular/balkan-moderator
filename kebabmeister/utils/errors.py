class ConfigKeyNotFound(Exception):
    def __init__(self, key):
        self.key = key

    def __str__(self):
        return f"Config key not found: {self.key}"
