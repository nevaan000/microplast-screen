"""Asset storage.

Every generated image, export and model artefact is addressed by a pathname and
kept either in a private Vercel Blob store or, when no store is configured, under
DATA_DIR. Serverless functions have no filesystem that survives an invocation, so
the blob backend is what runs in production; the local backend keeps `pytest` and
a laptop run working without Vercel credentials.

Pathnames are stored in the database exactly as returned by `put_asset`, so a row
written by one backend can be read by the other.
"""

from __future__ import annotations

import mimetypes
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, AsyncIterator

from starlette.concurrency import run_in_threadpool

from .config import config

# A Blob store is public or private for its whole lifetime and cannot be switched
# afterwards. This app serves every asset through an authenticated route, so the
# store must be private.
ACCESS = "private"
CHUNK_BYTES = 64 * 1024


class AssetNotFound(Exception):
    """Raised for a pathname that is not in the store."""


def _sync_blob() -> Any:
    from vercel.blob import sync as blob

    return blob


def _async_blob() -> Any:
    from vercel import blob

    return blob


def _local(pathname: str) -> Path:
    """Resolve a pathname under DATA_DIR, refusing anything that escapes it."""
    root = config.data_dir.resolve()
    target = (config.data_dir / pathname).resolve()
    if target != root and root not in target.parents:
        raise AssetNotFound(pathname)
    return target


def put_asset(pathname: str, data: bytes, content_type: str) -> str:
    if config.blob_enabled:
        result = _sync_blob().put_blob(
            pathname, data, access=ACCESS, content_type=content_type, allow_overwrite=True
        )
        return result.pathname
    target = _local(pathname)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return pathname


def read_asset(pathname: str) -> bytes:
    if config.blob_enabled:
        blob = _sync_blob()
        try:
            return blob.get_blob(pathname, access=ACCESS).body
        except blob.BlobNotFoundError as error:
            raise AssetNotFound(pathname) from error
    target = _local(pathname)
    if not target.is_file():
        raise AssetNotFound(pathname)
    return target.read_bytes()


def asset_exists(pathname: str) -> bool:
    if config.blob_enabled:
        blob = _sync_blob()
        try:
            blob.head_blob(pathname)
        except blob.BlobNotFoundError:
            return False
        return True
    try:
        return _local(pathname).is_file()
    except AssetNotFound:
        return False


def delete_assets(pathnames: list[str]) -> None:
    targets = [name for name in pathnames if name]
    if not targets:
        return
    if config.blob_enabled:
        # Deleting a blob that is already gone succeeds, so a retry is safe.
        _sync_blob().delete_blob(targets)
        return
    for name in targets:
        try:
            _local(name).unlink(missing_ok=True)
        except AssetNotFound:
            continue


def list_assets(prefix: str) -> list[str]:
    """Pathnames under a prefix, in ascending order."""
    if config.blob_enabled:
        return sorted(item.pathname for item in _sync_blob().query_blobs(prefix=prefix))
    folder_name, _, name_prefix = prefix.rpartition("/")
    folder = config.data_dir / folder_name if folder_name else config.data_dir
    if not folder.is_dir():
        return []
    return sorted(
        f"{folder_name}/{item.name}" if folder_name else item.name
        for item in folder.iterdir()
        if item.is_file() and item.name.startswith(name_prefix)
    )


async def stream_asset(pathname: str) -> tuple[str, AsyncIterator[bytes]]:
    """Return the content type and an async chunk iterator, raising AssetNotFound first.

    Vercel caps a buffered function response at 4.5 MB but exempts streamed ones,
    and a single annotated image is already close to that.
    """
    if config.blob_enabled:
        blob = _async_blob()
        stack = AsyncExitStack()
        try:
            download = await stack.enter_async_context(blob.stream_blob(pathname, access=ACCESS))
        except blob.BlobNotFoundError as error:
            await stack.aclose()
            raise AssetNotFound(pathname) from error
        except BaseException:
            await stack.aclose()
            raise
        return download.metadata.content_type or "application/octet-stream", _blob_chunks(download, stack)
    target = _local(pathname)
    if not target.is_file():
        raise AssetNotFound(pathname)
    content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    return content_type, _local_chunks(target)


async def _blob_chunks(download: Any, stack: AsyncExitStack) -> AsyncIterator[bytes]:
    async with stack:
        async for chunk in download:
            yield chunk


async def _local_chunks(path: Path) -> AsyncIterator[bytes]:
    data = await run_in_threadpool(path.read_bytes)
    for offset in range(0, len(data), CHUNK_BYTES):
        yield data[offset:offset + CHUNK_BYTES]
