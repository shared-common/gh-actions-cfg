#!/usr/bin/env python3
"""Find and optionally remove unavailable explicit source repositories.

The configuration repository contains one ``projects.yml`` file per mirror
collection.  This utility deliberately edits only active top-level project
entries in those files.  It never rewrites YAML through a serializer, so
comments and the existing formatting remain intact.
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import os
from dataclasses import dataclass
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import time
from typing import Callable, Iterable, Sequence
from urllib.parse import urlsplit


PROJECT_ITEM_RE = re.compile(r"^(?P<indent>\s*)-\s+name:\s*(?P<value>.*?)\s*$")
SOURCE_URL_RE = re.compile(r"^\s+source_project_url:\s*(?P<value>[^#]*?)(?:\s+#.*)?$")
TRANSIENT_ERROR_RE = re.compile(
    r"timed out|failed to connect|couldn't connect|connection reset|"
    r"connection refused|http\s+5\d\d|tls|temporarily unavailable|"
    r"remote end hung up",
    re.IGNORECASE,
)
MISSING_REPOSITORY_RE = re.compile(
    r"repository .*not found|project .*not found|not found|"
    r"does not appear to be a git repository|could not be found|"
    r"repository .*does not exist|http\s+404",
    re.IGNORECASE,
)
AUTH_ERROR_RE = re.compile(
    r"authentication failed|access denied|forbidden|could not read username|"
    r"permission denied",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ProjectEntry:
    collection: str
    config_path: Path
    name: str
    source_project_url: str
    target_group_path: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class ScanResult:
    project: ProjectEntry
    status: str
    checked_url: str
    detail: str = ""


def parse_scalar(value: str) -> str:
    """Decode the simple YAML scalars used by project names and URLs."""

    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        try:
            decoded = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value[1:-1]
        return decoded if isinstance(decoded, str) else str(decoded)
    return value


def _project_item_indent(lines: Sequence[str]) -> tuple[int, int] | None:
    projects_line = next(
        (index for index, line in enumerate(lines) if re.match(r"^projects:\s*(?:#.*)?$", line.rstrip("\n"))),
        None,
    )
    if projects_line is None:
        return None
    for index in range(projects_line + 1, len(lines)):
        match = PROJECT_ITEM_RE.match(lines[index].rstrip("\n"))
        if match:
            return index, len(match.group("indent"))
    return None


def parse_project_entries(config_path: Path, collection: str | None = None) -> list[ProjectEntry]:
    """Return active explicit project entries from one projects.yml file."""

    lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    first_item = _project_item_indent(lines)
    if first_item is None:
        return []
    first_index, item_indent = first_item
    starts = [
        index
        for index in range(first_index, len(lines))
        if (match := PROJECT_ITEM_RE.match(lines[index].rstrip("\n")))
        and len(match.group("indent")) == item_indent
    ]
    entries: list[ProjectEntry] = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = lines[start:end]
        name_match = PROJECT_ITEM_RE.match(block[0].rstrip("\n"))
        if not name_match:
            continue
        source_match = next(
            (
                match
                for line in block
                if (match := SOURCE_URL_RE.match(line.rstrip("\n")))
            ),
            None,
        )
        if source_match is None:
            continue
        name = parse_scalar(name_match.group("value"))
        source_url = parse_scalar(source_match.group("value"))
        target_group_path = ""
        for line in block:
            if line.lstrip().startswith("target_group_path:"):
                target_group_path = parse_scalar(line.split(":", 1)[1])
                break
        entries.append(
            ProjectEntry(
                collection=collection or config_path.parent.name,
                config_path=config_path,
                name=name,
                source_project_url=source_url,
                target_group_path=target_group_path,
                start_line=start,
                end_line=end,
            )
        )
    return entries


def collection_paths(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.iterdir()
        if path.is_dir() and path.name.startswith("glab-groups-")
    )


def parse_selection(value: str, collection_names: Sequence[str]) -> list[int]:
    """Parse ``all``, collection names, indexes, and inclusive index ranges."""

    value = value.strip()
    if value.lower() in {"all", "a"}:
        return list(range(len(collection_names)))
    selected: set[int] = set()
    by_name = {name: index for index, name in enumerate(collection_names)}
    for token in (part.strip() for part in value.split(",")):
        if not token:
            continue
        if token in by_name:
            selected.add(by_name[token])
            continue
        if re.fullmatch(r"\d+", token):
            index = int(token) - 1
            if 0 <= index < len(collection_names):
                selected.add(index)
                continue
        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", token)
        if range_match:
            start, end = (int(item) - 1 for item in range_match.groups())
            if 0 <= start <= end < len(collection_names):
                selected.update(range(start, end + 1))
                continue
        raise ValueError(f"invalid collection selection: {token}")
    if not selected:
        raise ValueError("select at least one collection")
    return sorted(selected)


def prompt_for_collections(
    collections: Sequence[Path],
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> list[Path]:
    if not collections:
        raise ValueError("no glab-groups-* collections were found")
    names = [path.name for path in collections]
    output_fn("Available collections:")
    for index, name in enumerate(names, start=1):
        output_fn(f"  {index}. {name}")
    while True:
        try:
            selection = input_fn("Select one or more collections (number, range, name, or all): ")
            indexes = parse_selection(selection, names)
            return [collections[index] for index in indexes]
        except EOFError as error:
            raise ValueError("input closed before a collection was selected") from error
        except ValueError as error:
            output_fn(str(error))


def _candidate_urls(source_url: str) -> list[str]:
    source_url = source_url.rstrip("/")
    parsed = urlsplit(source_url)
    if parsed.hostname and parsed.hostname.lower() == "hg.sr.ht":
        return [f"hg::{source_url}"]
    candidates = [source_url]
    if not source_url.endswith(".git"):
        candidates.append(f"{source_url}.git")
    return candidates


def _run_ls_remote(url: str, timeout_seconds: float) -> tuple[int, str]:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        completed = subprocess.run(
            ["git", "ls-remote", "--heads", "--tags", "--symref", url],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_seconds,
            env=environment,
        )
    except subprocess.TimeoutExpired as error:
        output = error.output or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return 124, f"git ls-remote timed out after {timeout_seconds:g}s\n{output}"
    except OSError as error:
        return 127, str(error)
    return completed.returncode, completed.stdout or ""


def scan_project(
    project: ProjectEntry,
    timeout_seconds: float = 30.0,
    retries: int = 2,
    runner: Callable[[str, float], tuple[int, str]] = _run_ls_remote,
    sleeper: Callable[[float], None] = time.sleep,
) -> ScanResult:
    last_output = ""
    last_url = project.source_project_url
    for candidate in _candidate_urls(project.source_project_url):
        last_url = candidate
        for attempt in range(max(1, retries)):
            return_code, output = runner(candidate, timeout_seconds)
            last_output = output.strip()
            if return_code == 0:
                return ScanResult(project, "available", candidate)
            if AUTH_ERROR_RE.search(output):
                return ScanResult(project, "error", candidate, last_output)
            if MISSING_REPOSITORY_RE.search(output):
                break
            if attempt + 1 < max(1, retries) and TRANSIENT_ERROR_RE.search(output):
                sleeper(min(2.0, 0.5 * (attempt + 1)))
                continue
            return ScanResult(project, "error", candidate, last_output)
    return ScanResult(project, "unavailable", last_url, last_output)


def scan_projects(
    projects: Sequence[ProjectEntry],
    workers: int = 8,
    timeout_seconds: float = 30.0,
    retries: int = 2,
) -> list[ScanResult]:
    if not projects:
        return []
    worker_count = max(1, min(workers, len(projects)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(scan_project, project, timeout_seconds, retries): index
            for index, project in enumerate(projects)
        }
        results = [None] * len(projects)
        for future in concurrent.futures.as_completed(futures):
            results[futures[future]] = future.result()
    return [result for result in results if result is not None]


def remove_project_entries(config_path: Path, entries: Iterable[ProjectEntry]) -> int:
    """Remove selected project blocks atomically and return the count removed."""

    selected = sorted(entries, key=lambda entry: entry.start_line, reverse=True)
    if not selected:
        return 0
    lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    for entry in selected:
        del lines[entry.start_line : entry.end_line]
    original_mode = stat.S_IMODE(config_path.stat().st_mode)
    content = "".join(lines)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=config_path.parent,
        prefix=f".{config_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary_path = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(temporary_path, original_mode)
        os.replace(temporary_path, config_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return len(selected)


def _print_result(result: ScanResult, output_fn: Callable[[str], None]) -> None:
    label = f"{result.project.collection}/{result.project.name}"
    if result.status == "available":
        output_fn(f"OK   {label}: {result.project.source_project_url}")
    elif result.status == "unavailable":
        output_fn(f"MISS {label}: {result.project.source_project_url}")
    else:
        output_fn(f"ERR  {label}: {result.project.source_project_url} ({result.detail})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan selected glab-groups collections and remove unavailable explicit source repositories."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="gh-actions-cfg root directory (defaults to the script directory)",
    )
    parser.add_argument("--workers", type=int, default=8, help="parallel source checks (default: 8)")
    parser.add_argument("--timeout", type=float, default=30.0, help="per-check timeout in seconds (default: 30)")
    parser.add_argument("--retries", type=int, default=2, help="attempts for transient failures (default: 2)")
    return parser


def main(
    argv: Sequence[str] | None = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.workers < 1 or args.timeout <= 0 or args.retries < 1:
        parser.error("workers, timeout, and retries must be positive")
    root = args.root.expanduser().resolve()
    collections = collection_paths(root)
    try:
        selected_collections = prompt_for_collections(collections, input_fn, output_fn)
    except ValueError as error:
        parser.error(str(error))

    projects: list[ProjectEntry] = []
    for collection in selected_collections:
        config_path = collection / "projects.yml"
        entries = parse_project_entries(config_path, collection.name) if config_path.exists() else []
        projects.extend(entries)
        output_fn(f"{collection.name}: {len(entries)} explicit source project(s)")

    results = scan_projects(projects, args.workers, args.timeout, args.retries)
    for result in results:
        _print_result(result, output_fn)
    unavailable = [result for result in results if result.status == "unavailable"]
    errors = [result for result in results if result.status == "error"]
    output_fn(f"Total unavailable repositories: {len(unavailable)}")
    if errors:
        output_fn(f"Checks requiring attention: {len(errors)}. These entries will not be removed automatically.")

    try:
        answer = input_fn(
            f"Remove the {len(unavailable)} unavailable repository entr{'y' if len(unavailable) == 1 else 'ies'} from configuration? [y/N]: "
        )
    except EOFError:
        answer = ""
    if answer.strip().lower() != "y":
        output_fn("No configuration entries were changed.")
        return 0

    removed = 0
    by_path: dict[Path, list[ProjectEntry]] = {}
    for result in unavailable:
        by_path.setdefault(result.project.config_path, []).append(result.project)
    for config_path, entries in by_path.items():
        count = remove_project_entries(config_path, entries)
        removed += count
        output_fn(f"Removed {count} unavailable entr{'y' if count == 1 else 'ies'} from {config_path}")
    output_fn(f"Removed {removed} unavailable entr{'y' if removed == 1 else 'ies'} in total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
