import pytest

from app.source.project import archive_from_files, files_from_archive, sample_project, safe_path


def test_sample_project_is_a_valid_editable_archive():
    archive, manifest = archive_from_files(sample_project("Demo MCP", "STDIO"))

    files = files_from_archive(archive)

    assert manifest["name"] == "Demo MCP"
    assert manifest["requirements"] == "requirements.txt"
    assert {"mcp.manifest.json", "server.py", "requirements.txt", ".env"} <= files.keys()


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", "folder/../secret"])
def test_project_paths_cannot_escape_the_archive(path):
    with pytest.raises(ValueError):
        safe_path(path)