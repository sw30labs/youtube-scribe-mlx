#!/usr/bin/env python3
"""Process saved YouTube links with the existing mode-2 LangGraph pipeline.

Only the standard library is loaded until a video needs transcription. Completed
videos are tracked by YouTube ID, independent of share/playlist parameters.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import html
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import tempfile
from typing import Callable
from urllib.parse import parse_qs, unquote, urlsplit
import uuid
from xml.parsers.expat import ExpatError


DEFAULT_INBOX = Path.home() / "Desktop" / "YouTubeToText"
SUFFIXES = {".txt", ".webloc", ".url"}
HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
         "youtu.be", "www.youtu.be", "youtube-nocookie.com", "www.youtube-nocookie.com"}
URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+|(?<![\w./@-])(?:www\.|m\.|music\.)?"
    r"(?:youtube\.com|youtu\.be|youtube-nocookie\.com)/[^\s<>\"']+", re.I
)


@dataclass(frozen=True)
class Video:
    video_id: str
    url: str


def canonical_video(value: str) -> Video:
    value = html.unescape(value.strip()).rstrip(".,;!?)]}")
    if "://" not in value:
        value = "https://" + value
    parsed = urlsplit(value)
    if (parsed.scheme.lower() not in {"https", "http"}
            or parsed.hostname not in HOSTS or parsed.username or parsed.password
            or parsed.port not in {None, 80, 443}):
        raise ValueError("Use a YouTube video Share link.")
    parts = unquote(parsed.path).strip("/").split("/")
    query = parse_qs(parsed.query)
    video_id = ""
    if parsed.hostname in {"youtu.be", "www.youtu.be"} and len(parts) == 1:
        video_id = parts[0]
    elif parts == ["watch"]:
        video_id = query.get("v", [""])[0]
    elif len(parts) == 2 and parts[0] in {"shorts", "live", "embed", "v"}:
        video_id = parts[1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("The link must identify one video. Open the video and copy its Share link.")
    return Video(video_id, f"https://www.youtube.com/watch?v={video_id}")


def videos_from_text(text: str) -> tuple[list[Video], list[str]]:
    videos: dict[str, Video] = {}
    errors = []
    candidates = URL_PATTERN.findall(html.unescape(text))
    for candidate in candidates:
        try:
            video = canonical_video(candidate)
            videos[video.video_id] = video
        except ValueError as exc:
            errors.append(f"{candidate}: {exc}")
    if not candidates:
        errors.append("No YouTube video link found.")
    return list(videos.values()), errors


def read_drop(path: Path) -> str:
    if path.stat().st_size > 2_000_000:
        raise ValueError("Link file is too large (maximum 2 MB).")
    data = path.read_bytes()
    if path.suffix.lower() == ".webloc":
        value = plistlib.loads(data)
        if not isinstance(value, dict) or not isinstance(value.get("URL"), str):
            raise ValueError("This .webloc file does not contain a URL.")
        return value["URL"]
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    return data.decode("utf-8-sig")


def scan_inbox(inbox: Path) -> tuple[list[Video], list[str]]:
    videos: dict[str, Video] = {}
    errors = []
    for path in sorted(inbox.iterdir(), key=lambda p: p.name.casefold()):
        if path.name.startswith(".") or path.suffix.lower() not in SUFFIXES or not path.is_file():
            continue
        try:
            found, invalid = videos_from_text(read_drop(path))
            for video in found:
                videos[video.video_id] = video
            errors.extend(f"{path.name}: {error}" for error in invalid)
        except (OSError, ValueError, plistlib.InvalidFileException, ExpatError) as exc:
            errors.append(f"{path.name}: {exc}")
    return list(videos.values()), errors


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def enqueue_text(inbox: Path, value: str) -> list[Video]:
    videos, errors = videos_from_text(value)
    # Clipboard is an explicit action: reject the entire input if any URL is bad.
    if errors:
        raise ValueError("\n".join(errors))
    for video in videos:
        atomic_write(inbox / f"YouTube-{video.video_id}.txt", (video.url + "\n").encode("utf-8"))
        print(f"Added: {video.url}", flush=True)
    return videos


@contextmanager
def processing_lock(inbox: Path):
    with (inbox / ".processing.lock").open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("YouTubeToText is already processing this folder. Run it again afterward for newly added links.") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def load_registry(inbox: Path) -> dict:
    path = inbox / ".processed.json"
    if not path.exists():
        return {"version": 1, "completed": {}}
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(registry, dict) or registry.get("version") != 1 or not isinstance(registry.get("completed"), dict):
            raise ValueError("unrecognized format")
        for key, value in registry["completed"].items():
            if not re.fullmatch(r"[A-Za-z0-9_-]{11}", key) or not isinstance(value, dict):
                raise ValueError("invalid completed-video entry")
        return registry
    except (ValueError, OSError) as exc:
        raise RuntimeError(f"Cannot read processing history at {path}: {exc}. Preserve this file and repair it before continuing.") from exc


def completed_output(inbox: Path, record: dict | None) -> Path | None:
    if not record or not isinstance(record.get("text_file"), str):
        return None
    path = inbox / "output" / record["text_file"]
    try:
        if path.parent.resolve() != (inbox / "output").resolve() or path.is_symlink():
            return None
        if path.is_file() and path.stat().st_size and path.read_text(encoding="utf-8").strip():
            return path
    except (OSError, UnicodeError):
        pass
    return None


def validated_artifact(video: Video, job_dir: Path) -> Path | None:
    """Require matching source, real transcript and a complete standard TXT."""
    for metadata in sorted(job_dir.glob("*.json")):
        try:
            data = json.loads(metadata.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("video_info"), dict):
                continue
            source = canonical_video(data["video_info"].get("url", ""))
            transcript = data.get("transcript")
            if source != video or not isinstance(transcript, str) or not transcript.strip() or transcript == "ALREADY_PROCESSED":
                continue
            txt = metadata.with_suffix(".txt")
            content = txt.read_text(encoding="utf-8")
            section = content.rsplit("\nTranscript:\n" + "-" * 20 + "\n", 1)
            expected = "\n".join(s.strip() + "." for s in transcript.replace("...", ".").split(".") if s.strip())
            if len(section) == 2 and expected and section[1].strip() == expected:
                return txt
        except (OSError, ValueError, AttributeError, TypeError):
            continue
    return None


def preserve_incomplete_artifacts(job_dir: Path) -> None:
    leftovers = list(job_dir.glob("*.json")) + list(job_dir.glob("*.txt"))
    if leftovers:
        recovery = job_dir / ".incomplete" / uuid.uuid4().hex
        recovery.mkdir(parents=True)
        for path in leftovers:
            path.rename(recovery / path.name)


def graph_state(video: Video, job_dir: Path, stt: str | None = None) -> dict:
    from stt import graph_backend, resolve_choice

    choice = resolve_choice(stt)
    return {
        "url": video.url, "is_playlist": False, "audio_only": False,
        "save_video": False, "is_local_file": False, "playlist_info": None,
        "output_dir": str(job_dir.resolve()), "video_urls": [(video.url, "unknown")],
        "current_index": 0, "current_video_url": None, "current_video_title": None,
        "audio_dir": None, "video_dir": None, "video_info": None,
        "audio_path": None, "video_path": None, "audio_analysis": None,
        "audio_metrics": None, "audio_features": None, "transcript": None,
        "video_transcripts": [], "diarization_segments": None,
        "pascal_speaker_id": None, "reference_audio_path": None,
        "pascal_segments": None, "transcription_backend": graph_backend(choice),
        "stt_model": choice.key,
    }


def run_graph(video: Video, job_dir: Path, stt: str | None = None) -> None:
    import main_langgraph as pipeline
    from filename_utils import invalidate_transcript_index
    from stt import cleanup_all

    invalidate_transcript_index(str(job_dir.resolve()))
    try:
        pipeline.app.invoke(graph_state(video, job_dir, stt), {"recursion_limit": 1000})
    finally:
        cleanup_all()


def export_transcript(video: Video, artifact: Path, inbox: Path) -> Path:
    # Cap UTF-8 bytes so the title plus ID fits the macOS filename limit.
    title = re.sub(r'[/:\x00-\x1f\x7f]', "_", artifact.stem).strip(" .") or "YouTube"
    title = title.encode("utf-8")[:180].decode("utf-8", errors="ignore")
    destination = inbox / "output" / f"{title} [{video.video_id}].txt"
    atomic_write(destination, artifact.read_bytes())
    return destination


def process_batch(inbox: Path, *, dry_run: bool = False,
                  processor: Callable[[Video, Path], None] | None = None,
                  stt: str | None = None) -> tuple[int, list[Path]]:
    if processor is None:
        def processor(video: Video, job_dir: Path, _stt: str | None = stt) -> None:
            run_graph(video, job_dir, _stt)
    registry = load_registry(inbox)
    videos, errors = scan_inbox(inbox)
    for error in errors:
        print(f"LINK ERROR: {error}", file=sys.stderr, flush=True)
    successful, skipped, failed = [], 0, len(errors)
    for index, video in enumerate(videos, 1):
        existing = completed_output(inbox, registry["completed"].get(video.video_id))
        if existing:
            print(f"Already completed: {existing.name}", flush=True)
            skipped += 1
            continue
        print(f"[{index}/{len(videos)}] {'Pending' if dry_run else 'Processing'}: {video.url}", flush=True)
        if dry_run:
            continue
        try:
            job_dir = inbox / ".work" / video.video_id
            job_dir.mkdir(parents=True, exist_ok=True)
            artifact = validated_artifact(video, job_dir)
            if artifact is None:
                # A failed write must never cause the original graph to skip retry.
                preserve_incomplete_artifacts(job_dir)
                processor(video, job_dir)
                artifact = validated_artifact(video, job_dir)
            if artifact is None:
                raise RuntimeError("No complete text transcript was produced. See the download/transcription messages above; this video will retry on the next run.")
            destination = export_transcript(video, artifact, inbox)
            registry["completed"][video.video_id] = {
                "url": video.url, "text_file": destination.name,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            atomic_write(inbox / ".processed.json", (json.dumps(registry, indent=2) + "\n").encode("utf-8"))
            successful.append(destination)
            print(f"Saved text: {destination}", flush=True)
        except Exception as exc:
            failed += 1
            print(f"FAILED {video.url}: {exc}", file=sys.stderr, flush=True)
    if dry_run:
        print(f"Queue checked: {len(videos)} unique video(s), {skipped} already completed, {failed} link error(s).")
    else:
        print(f"Finished: {len(successful)} saved, {skipped} already completed, {failed} error(s).", flush=True)
    if not videos:
        print(f"Drop .webloc, .url or .txt link files into {inbox}, or choose Add copied link in the app.")
    return (1 if failed else 0), successful


def open_results(inbox: Path, paths: list[Path]) -> None:
    if len(paths) == 1:
        command = ["/usr/bin/open", "-a", "TextEdit", str(paths[0])]
    else:
        output = inbox / "output"
        command = ["/usr/bin/open", str(output if output.exists() else inbox)]
    subprocess.run(command, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox", type=Path, default=Path(os.environ.get("YOUTUBE_INBOX_DIR", str(DEFAULT_INBOX))))
    parser.add_argument("--add-clipboard", action="store_true", help="Save YouTube links currently copied to the clipboard")
    parser.add_argument("--enqueue-only", action="store_true", help="Only add copied links; do not start processing")
    parser.add_argument("--dry-run", action="store_true", help="Show pending videos without downloading or transcribing")
    parser.add_argument("--open-output", action="store_true", help="Open the new transcript in TextEdit, or show the output folder")
    from stt import add_stt_argument, resolve_choice, save_stt
    add_stt_argument(parser)
    args = parser.parse_args(argv)
    if args.enqueue_only and not args.add_clipboard:
        parser.error("--enqueue-only requires --add-clipboard")
    if args.dry_run and args.add_clipboard:
        parser.error("--dry-run cannot be combined with --add-clipboard")
    inbox = args.inbox.expanduser().resolve()
    try:
        inbox.mkdir(parents=True, exist_ok=True)
        if args.add_clipboard:
            clipboard = subprocess.run(["/usr/bin/pbpaste"], capture_output=True, check=True, encoding="utf-8").stdout
            enqueue_text(inbox, clipboard)
        if args.enqueue_only:
            return 0
        if args.stt and args.save_stt:
            save_stt(args.stt, inbox=inbox)
        stt = resolve_choice(args.stt, inbox=inbox).key
        if not args.dry_run and not args.enqueue_only:
            print(f"STT: {resolve_choice(stt).label} ({resolve_choice(stt).model_id})", flush=True)
        with processing_lock(inbox):
            status, paths = process_batch(inbox, dry_run=args.dry_run, stt=stt)
        if args.open_output and not args.dry_run:
            try:
                open_results(inbox, paths)
            except (OSError, subprocess.CalledProcessError) as exc:
                print(f"Text files were saved, but could not open the window: {exc}", file=sys.stderr)
        return status
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped. Completed videos are saved; unfinished videos will retry next time.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
