import bcrypt


MAX_PASSWORD_BYTES = 72


def validate_password_length(password: str) -> str:
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(
            "Password cannot be longer than 72 bytes. "
            "Please use a shorter password."
        )
    return password


def hash_password(password: str) -> str:
    validated_password = validate_password_length(password)
    password_bytes = validated_password.encode("utf-8")

    salt = bcrypt.gensalt()

    hashed = bcrypt.hashpw(
        password_bytes,
        salt,
    )

    return hashed.decode("utf-8")


def verify_password(
        plain_password: str,
        hashed_password: str,
    ) -> bool:
    validate_password_length(plain_password)

    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )