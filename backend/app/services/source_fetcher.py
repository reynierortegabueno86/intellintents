"""Fetch dataset/taxonomy content from a URL or server file path."""

import asyncio
import os
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import httpx


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SourceFetchError(Exception):
    """Base exception for source fetch errors."""


class SourceTimeoutError(SourceFetchError):
    """The request timed out."""


class SourceConnectionError(SourceFetchError):
    """Could not connect to the remote host."""


class SourceNotFoundError(SourceFetchError):
    """The resource was not found (404 or missing file)."""


class SourceTooLargeError(SourceFetchError):
    """The resource exceeds the maximum allowed size."""


class SourcePathNotAllowedError(SourceFetchError):
    """The local path is not in the allowed directories."""


class SourceInvalidError(SourceFetchError):
    """The source string is not a valid URL or path."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONTENT_TYPE_EXT = {
    "text/csv": "csv",
    "application/json": "json",
    "application/x-ndjson": "jsonl",
    "application/jsonl": "jsonl",
}


def _filename_from_url(url: str, content_type: str | None = None) -> str:
    """Extract a filename from a URL path, falling back to Content-Type."""
    path = urlparse(url).path.rstrip("/")
    basename = path.rsplit("/", 1)[-1] if path else ""
    if basename and "." in basename:
        return basename
    # Fallback: infer extension from Content-Type
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        ext = _CONTENT_TYPE_EXT.get(ct)
        if ext:
            return f"download.{ext}"
    return basename or "download"


# ---------------------------------------------------------------------------
# Main fetch function
# ---------------------------------------------------------------------------

async def fetch_source(
    source: str, max_bytes: int = 50 * 1024 * 1024
) -> tuple[bytes, str]:
    """Fetch from HTTP/HTTPS/FTP URL or server file path.

    Returns (content_bytes, filename).
    """
    source = source.strip()
    if not source:
        raise SourceInvalidError("Source must not be empty")

    parsed = urlparse(source)
    scheme = parsed.scheme.lower()

    if scheme in ("http", "https"):
        return await _fetch_http(source, max_bytes)
    elif scheme == "ftp":
        return await _fetch_ftp(source, max_bytes)
    elif scheme in ("", "file"):
        if scheme == "":
            local_path = source
        else:
            # file:///path → netloc="", path="/path"  (correct)
            # file://path  → netloc="path-segment", path="/rest"  (common mistake)
            # Reconstruct full path from both to handle either form.
            local_path = f"/{parsed.netloc}{parsed.path}" if parsed.netloc else parsed.path
        return await _fetch_local(local_path, max_bytes)
    else:
        raise SourceInvalidError(f"Unsupported scheme: {scheme}")


async def _fetch_http(url: str, max_bytes: int) -> tuple[bytes, str]:
    try:
        async with httpx.AsyncClient(
            timeout=30, follow_redirects=True
        ) as client:
            async with client.stream("GET", url) as response:
                if response.status_code == 404:
                    raise SourceNotFoundError(f"Not found: {url}")
                response.raise_for_status()

                # Check Content-Length header if present
                content_length = response.headers.get("content-length")
                if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                    raise SourceTooLargeError(
                        f"File too large ({int(content_length)} bytes). "
                        f"Maximum allowed: {max_bytes} bytes."
                    )

                # Stream and accumulate chunks
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise SourceTooLargeError(
                            f"File exceeds maximum size of {max_bytes} bytes."
                        )
                    chunks.append(chunk)

                content = b"".join(chunks)
                content_type = response.headers.get("content-type")
                filename = _filename_from_url(url, content_type)
                return content, filename

    except SourceFetchError:
        raise
    except httpx.TimeoutException:
        raise SourceTimeoutError(f"Request timed out: {url}")
    except httpx.ConnectError:
        raise SourceConnectionError(f"Could not connect to: {url}")
    except httpx.HTTPStatusError as exc:
        raise SourceFetchError(
            f"HTTP error {exc.response.status_code} fetching {url}"
        )
    except httpx.HTTPError as exc:
        raise SourceConnectionError(f"HTTP error fetching {url}: {exc}")


async def _fetch_ftp(url: str, max_bytes: int) -> tuple[bytes, str]:
    def _do_fetch():
        resp = urllib.request.urlopen(url, timeout=30)  # noqa: S310
        data = resp.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise SourceTooLargeError(
                f"File exceeds maximum size of {max_bytes} bytes."
            )
        return data

    try:
        data = await asyncio.to_thread(_do_fetch)
    except SourceFetchError:
        raise
    except TimeoutError:
        raise SourceTimeoutError(f"FTP request timed out: {url}")
    except Exception as exc:
        raise SourceConnectionError(f"FTP error fetching {url}: {exc}")

    filename = _filename_from_url(url)
    return data, filename


def _default_allowed_paths() -> str:
    """Return sensible default allowed directories: home dir + /tmp."""
    home = Path.home()
    return f"{home},{os.sep}tmp"


async def _fetch_local(path_str: str, max_bytes: int) -> tuple[bytes, str]:
    allowed_env = os.environ.get("ALLOWED_FILE_PATHS", "").strip()
    if not allowed_env:
        allowed_env = _default_allowed_paths()

    allowed_dirs = [
        Path(d.strip()).resolve() for d in allowed_env.split(",") if d.strip()
    ]
    resolved = Path(path_str).resolve()

    if not any(
        resolved == allowed or resolved.is_relative_to(allowed)
        for allowed in allowed_dirs
    ):
        raise SourcePathNotAllowedError(
            f"Path '{path_str}' is not under any allowed directory. "
            f"Allowed: {', '.join(str(d) for d in allowed_dirs)}"
        )

    if not resolved.is_file():
        raise SourceNotFoundError(f"File not found: {path_str}")

    size = resolved.stat().st_size
    if size > max_bytes:
        raise SourceTooLargeError(
            f"File too large ({size} bytes). Maximum allowed: {max_bytes} bytes."
        )

    data = await asyncio.to_thread(resolved.read_bytes)
    return data, resolved.name
