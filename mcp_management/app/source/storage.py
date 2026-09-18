from pathlib import Path


class ArtifactNotFoundError(FileNotFoundError):
    pass


class SourceArtifactStore:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, digest: str, content: bytes) -> str:
        artifact = self.root / f"{digest}.zip"
        if not artifact.exists():
            temporary = artifact.with_suffix(".tmp")
            temporary.write_bytes(content)
            temporary.replace(artifact)
        return str(artifact)

    def get(self, digest: str) -> bytes:
        artifact = self.root / f"{digest}.zip"
        if not artifact.is_file():
            raise ArtifactNotFoundError(digest)
        return artifact.read_bytes()