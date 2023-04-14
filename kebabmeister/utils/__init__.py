from kebabmeister import state


def is_whitelisted(user: str, whitelist: list[str]) -> bool:
    return user == state.me.name or user in whitelist
