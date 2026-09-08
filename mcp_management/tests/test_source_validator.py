import io
import json
import zipfile

import pytest

from app.source.validator import ArchiveValidationError, validate_zip_archive


def make_archive(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for filename, content in entries.items():
            archive.writestr(filename, content)
    return output.getvalue()


def valid_manifest() -> bytes:
    return json.dumps({"name": "example", "command": ["python", "server.py"]}).encode()


def test_validate_zip_returns_digest_and_manifest():
    content = make_archive({"mcp.manifest.json": valid_manifest(), "server.py": b"print('ok')"})

    result = validate_zip_archive(content)

    assert len(result.digest) == 64
    assert result.manifest["name"] == "example"
    assert result.filenames == ("mcp.manifest.json", "server.py")


@pytest.mark.parametrize("filename", ["../escape.txt", "/absolute.txt", "nested/../../escape.txt"])
def test_validate_zip_rejects_unsafe_paths(filename: str):
    content = make_archive({"mcp.manifest.json": valid_manifest(), filename: b"bad"})

    with pytest.raises(ArchiveValidationError, match="unsafe path"):
        validate_zip_archive(content)


def test_validate_zip_requires_manifest_command():
    content = make_archive({"mcp.manifest.json": b'{"name":"missing-command"}'})

    with pytest.raises(ArchiveValidationError, match="command list"):
        validate_zip_archive(content)
