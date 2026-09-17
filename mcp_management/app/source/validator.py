import hashlib
import io
import json
import posixpath
import stat
import zipfile
from dataclasses import dataclass


MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_FILES = 1_000
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_PATH_DEPTH = 20
MANIFEST_NAME = "mcp.manifest.json"


class ArchiveValidationError(ValueError):
    """Raised when an uploaded MCP source archive is unsafe or invalid."""


@dataclass(frozen=True)
class ValidatedArchive:
    digest: str
    manifest: dict[str, object]
    filenames: tuple[str, ...]


def validate_zip_archive(content: bytes) -> ValidatedArchive:
    if len(content) > MAX_ARCHIVE_BYTES:
        raise ArchiveValidationError("source archive exceeds the maximum size")
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as error:
        raise ArchiveValidationError("source archive is not a valid ZIP file") from error

    with archive:
        entries = archive.infolist()
        if not entries:
            raise ArchiveValidationError("source archive is empty")
        if len(entries) > MAX_FILES:
            raise ArchiveValidationError("source archive contains too many files")

        total_size = 0
        filenames: list[str] = []
        manifest_info = None
        for entry in entries:
            normalized = posixpath.normpath(entry.filename)
            parts = normalized.split("/")
            if entry.filename.startswith(("/", "\\")) or ".." in parts or normalized != entry.filename:
                raise ArchiveValidationError("source archive contains an unsafe path")
            if len(parts) > MAX_PATH_DEPTH:
                raise ArchiveValidationError("source archive path is too deep")
            if stat.S_ISLNK((entry.external_attr >> 16) & 0xFFFF):
                raise ArchiveValidationError("source archive contains a symbolic link")
            if entry.is_dir():
                continue
            total_size += entry.file_size
            if total_size > MAX_UNCOMPRESSED_BYTES:
                raise ArchiveValidationError("source archive expands beyond the maximum size")
            filenames.append(entry.filename)
            if entry.filename == MANIFEST_NAME:
                manifest_info = entry

        if manifest_info is None:
            raise ArchiveValidationError(f"source archive must contain {MANIFEST_NAME}")
        try:
            manifest = json.loads(archive.read(manifest_info))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ArchiveValidationError("source manifest is not valid JSON") from error
        if not isinstance(manifest, dict):
            raise ArchiveValidationError("source manifest must be a JSON object")
        if not isinstance(manifest.get("name"), str) or not manifest["name"].strip():
            raise ArchiveValidationError("source manifest requires a name")
        if not isinstance(manifest.get("command"), list) or not manifest["command"]:
            raise ArchiveValidationError("source manifest requires a command list")
        if not all(isinstance(argument, str) and argument for argument in manifest["command"]):
            raise ArchiveValidationError("source manifest command arguments must be non-empty strings")

    return ValidatedArchive(
        digest=hashlib.sha256(content).hexdigest(),
        manifest=manifest,
        filenames=tuple(filenames),
    )