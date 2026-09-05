from agent_auth import hash_password, validate_password, verify_password


def validate_password_length(password: str) -> str:
    return validate_password(password)