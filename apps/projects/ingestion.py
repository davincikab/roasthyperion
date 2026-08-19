import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

from .models import Project

ALLOWED_EXTENSIONS = {".zip"}


class IngestError(Exception):
    pass


def list_pending_files(project: Project) -> list[dict]:
    """Files sitting in this project's FTP landing folder, ready to be ingested."""
    directory = project.landing_dir
    if not directory.exists():
        return []
    return [
        {"name": path.name, "size": path.stat().st_size}
        for path in sorted(directory.iterdir())
        if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS
    ]


def resolve_landing_file(project: Project, filename: str) -> Path:
    """Resolve `filename` to a path strictly inside the project's landing folder.

    `filename` must be a bare filename (no path separators) so this can't be used
    to reach outside the landing directory — it should only ever come from a
    choice already offered by list_pending_files(), never free-typed input.
    """
    if not filename or "/" in filename or "\\" in filename:
        raise IngestError("Invalid filename.")
    landing_dir = project.landing_dir.resolve()
    candidate = (landing_dir / filename).resolve()
    if landing_dir not in candidate.parents or not candidate.is_file():
        raise IngestError("File not found in this project's landing folder.")
    if candidate.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise IngestError(f"Unsupported file type: {candidate.suffix}")
    return candidate


def _safe_extract(zf: zipfile.ZipFile, target: Path) -> None:
    """Extract `zf` into `target`, rejecting any member that would land outside it."""
    target = target.resolve()
    for member in zf.infolist():
        member_path = (target / member.filename).resolve()
        if member_path != target and target not in member_path.parents:
            raise IngestError(f"Unsafe path in zip archive: {member.filename}")
    zf.extractall(target)


def _find_tiles_root(extracted_dir: Path) -> Path:
    """Locate the directory that directly contains zoom-level folders (e.g. '14', '15').

    Handles both a zip with the zoom folders at its root, and one with a single
    wrapper folder around them (i.e. someone zipped the parent directory).
    """
    candidates = [extracted_dir, *(p for p in extracted_dir.iterdir() if p.is_dir())]
    for candidate in candidates:
        if any(child.is_dir() and child.name.isdigit() for child in candidate.iterdir()):
            return candidate
    raise IngestError("No zoom-level folders (e.g. '14', '15', ...) found in the uploaded zip.")


def run_ingestion(project: Project, filename: str) -> None:
    """Validate, extract the tile pyramid into place, and archive the source zip.

    Raises IngestError (or lets underlying exceptions propagate) on failure —
    callers are responsible for catching and recording that on the Project.
    """
    source_path = resolve_landing_file(project, filename)

    if not zipfile.is_zipfile(source_path):
        raise IngestError("Uploaded file is not a valid zip archive.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        extracted_dir = Path(tmp_dir) / "extracted"
        with zipfile.ZipFile(source_path) as zf:
            _safe_extract(zf, extracted_dir)

        tiles_root = _find_tiles_root(extracted_dir)

        destination = project.tiles_dir
        if destination.exists():
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tiles_root), str(destination))

    project.tiles_version = uuid.uuid4().hex
    project.status = Project.Status.READY
    project.ingest_error = ""
    project.save()

    archive_dir = project.landing_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_path), str(archive_dir / source_path.name))
