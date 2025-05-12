#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
import argparse
import glob
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import anyio
import anyio.to_thread
import httpx

GREY = "\033[90m"
GREEN = "\033[92m"
RED = "\033[91m"
_END = "\033[0m"
_URL_RE = re.compile(r'https?://[^\s<>"\')\]]+', re.IGNORECASE)


@dataclass(slots=True)
class LinkResult:
    url: str
    status: int | None
    ok: bool
    sources: frozenset[Path]
    error: str | None = None


async def extract_links(path: Path) -> set[str]:
    try:
        content = await anyio.to_thread.run_sync(path.read_text, "utf-8", "ignore")
        return {m.group(0).rstrip(".,)") for m in _URL_RE.finditer(content)}
    except Exception:
        return set()


async def _probe(client: httpx.AsyncClient, url: str) -> LinkResult:
    try:
        r = await client.head(url, follow_redirects=True)
        if r.status_code in {405, 403}:
            r = await client.get(url, follow_redirects=True)
        return LinkResult(url, r.status_code, 200 <= r.status_code < 400, frozenset())
    except Exception as exc:
        return LinkResult(url, None, False, frozenset(), str(exc))


async def check_links(urls: Iterable[str], concurrency: int) -> list[LinkResult]:
    sem = anyio.Semaphore(concurrency)
    results: list[LinkResult] = []

    async with httpx.AsyncClient(timeout=10) as client:

        async def bound(u: str) -> None:
            async with sem:
                results.append(await _probe(client, u))

        async with anyio.create_task_group() as tg:
            for url in urls:
                tg.start_soon(bound, url)

    return results


async def audit(
    paths: set[Path],
    ignored_prefixes: tuple[str, ...],
    concurrency: int,
) -> list[LinkResult]:
    link_to_files: dict[str, set[Path]] = {}

    async def process_file(p: Path) -> None:
        for url in await extract_links(p):
            if any(url.startswith(pref) for pref in ignored_prefixes):
                continue
            if re.search(r"{[^}]+}", url):  # skip template tokens like {var}
                continue
            link_to_files.setdefault(url, set()).add(p)

    chunk_size = 100
    for i in range(0, len(paths), chunk_size):
        paths_chunk = list(paths)[i : i + chunk_size]
        async with anyio.create_task_group() as tg:
            for path in paths_chunk:
                tg.start_soon(process_file, path)

    return [
        LinkResult(
            url=r.url,
            status=r.status,
            ok=r.ok,
            sources=frozenset(link_to_files[r.url]),
            error=r.error,
        )
        for r in await check_links(link_to_files, concurrency)
    ]


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fail the build if any HTTP link is unreachable."
    )
    parser.add_argument("include", nargs="+", help="Glob pattern(s) to scan.")
    parser.add_argument(
        "--exclude", nargs="*", default=[], help="Glob pattern(s) to skip."
    )
    parser.add_argument(
        "--ignore-url",
        nargs="*",
        default=("http://localhost", "https://localhost"),
        metavar="PREFIX",
        help="URL prefixes to ignore.",
    )
    parser.add_argument("-c", "--concurrency", type=int, default=50)

    ns = parser.parse_args()

    include = {Path(p) for pat in ns.include for p in glob.glob(pat, recursive=True)}
    exclude = {Path(p) for pat in ns.exclude for p in glob.glob(pat, recursive=True)}

    if not (files := include - exclude):
        print("No files to scan.", file=sys.stderr)
        sys.exit(2)

    links = await audit(files, tuple(ns.ignore_url), concurrency=ns.concurrency)

    broken_links: list[LinkResult] = []
    for r in sorted(links, key=lambda x: sorted(x.sources)[0].as_posix()):
        status = r.status or "ERR"
        icon = f"{GREEN}✓{_END}" if r.ok else f"{RED}✗{_END}"
        url_repr = r.url if r.ok else f"{RED}{r.url}{_END}"
        srcs = ", ".join(s.as_posix() for s in sorted(r.sources))

        print(f"{GREY}{srcs}:{_END} {status:>4} {icon} {url_repr}")

        if not r.ok:
            broken_links.append(r)

    if broken_links:
        print(f"\n{len(broken_links)} broken link(s) detected.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    anyio.run(main)
