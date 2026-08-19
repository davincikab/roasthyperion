"""Shared test helpers for building sample tile-pyramid zip archives."""

import base64
import zipfile
from pathlib import Path

# A valid, minimal 1x1 transparent PNG — enough to exercise real file I/O in
# tests without needing an image library.
_SAMPLE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY"
    "42YAAAAASUVORK5CYII="
)


def write_sample_tile_zip(path, zoom_levels=(14,), tiles_per_level=((0, 0), (0, 1))):
    """Write a zip at `path` containing a tiny {z}/{x}/{y}.png tile pyramid."""
    with zipfile.ZipFile(path, "w") as zf:
        for z in zoom_levels:
            for x, y in tiles_per_level:
                zf.writestr(f"{z}/{x}/{y}.png", _SAMPLE_PNG)


def write_tile(tiles_dir: Path, z: int, x: int, y: int) -> Path:
    """Write a single sample tile directly to `tiles_dir` (bypassing ingestion)."""
    tile_path = tiles_dir / str(z) / str(x) / f"{y}.png"
    tile_path.parent.mkdir(parents=True, exist_ok=True)
    tile_path.write_bytes(_SAMPLE_PNG)
    return tile_path
