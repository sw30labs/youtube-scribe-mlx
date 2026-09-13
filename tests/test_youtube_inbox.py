"""Behavior checks for the folder queue, without YouTube or model access."""
from __future__ import annotations

import json
from pathlib import Path
import plistlib
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import youtube_inbox as inbox_app


FIRST = "XXel6Dnxb-k"
SECOND = "zXPpgajslJI"
FIRST_URL = f"https://www.youtube.com/watch?v={FIRST}"
SECOND_URL = f"https://www.youtube.com/watch?v={SECOND}"


def put_drop(inbox: Path, text: str, name: str = "links.txt") -> Path:
    path = inbox / name
    path.write_text(text, encoding="utf-8")
    return path


def write_artifact(video: inbox_app.Video, job: Path, title: str = "Fixture") -> Path:
    """Create the same externally visible pair produced by graph.save_node."""
    job.mkdir(parents=True, exist_ok=True)
    metadata = {
        "video_info": {"title": title, "url": video.url, "duration": 21},
        "audio_analysis": None,
        "transcript": "The first sentence. A second sentence!",
        "audio_file": f"{title}.wav",
        "video_file": None,
        "mode": "full",
    }
    (job / f"{title}.json").write_text(json.dumps(metadata), encoding="utf-8")
    txt = job / f"{title}.txt"
    txt.write_text(
        f"Video Analysis: {title}\n"
        + "=" * 80
        + f"\n\nVideo Information:\n--------------------\nURL: {video.url}\n"
        + f"Title: {title}\nDuration: 21 seconds\nAudio File: {title}.wav\n\n"
        + "Transcript:\n--------------------\nThe first sentence.\nA second sentence!.\n\n\n",
        encoding="utf-8",
    )
    return txt


@pytest.mark.parametrize("link", [
    f"https://youtu.be/{FIRST}?si=tracking",
    f"https://www.youtube.com/watch?v={FIRST}&list=PL_whole_playlist&index=5",
    f"https://youtube.com/watch?list=RDmix&v={FIRST}&start_radio=1",
    f"https://m.youtube.com/shorts/{FIRST}?feature=share",
    f"https://youtube.com/live/{FIRST}?si=tracking",
    f"https://www.youtube-nocookie.com/embed/{FIRST}",
    f"http://music.youtube.com/watch?v={FIRST}",
    f"www.youtube.com/watch?v={FIRST}&amp;list=RDmix",
])
def test_canonical_video_discards_playlist_and_tracking(link):
    assert inbox_app.canonical_video(link) == inbox_app.Video(FIRST, FIRST_URL)


@pytest.mark.parametrize("link", [
    f"https://youtube.com.evil.example/watch?v={FIRST}",
    f"https://evilyoutube.com/watch?v={FIRST}",
    f"https://youtube.com@evil.example/watch?v={FIRST}",
    f"https://user@youtube.com/watch?v={FIRST}",
    f"file://youtube.com/watch?v={FIRST}",
    f"https://youtube.com:444/watch?v={FIRST}",
    "https://youtube.com/playlist?list=PL_whole_playlist",
    "https://youtube.com/watch?v=short",
])
def test_canonical_video_rejects_other_hosts_and_non_video_inputs(link):
    with pytest.raises(ValueError):
        inbox_app.canonical_video(link)


def test_scan_accepts_text_webloc_url_and_deduplicates_ids(tmp_path):
    put_drop(tmp_path, f"Interesting videos:\n{FIRST_URL}\n{SECOND_URL}\n", "a.txt")
    (tmp_path / "b.webloc").write_bytes(plistlib.dumps({"URL": f"https://youtu.be/{FIRST}?si=x"}))
    (tmp_path / "c.URL").write_bytes(
        f"[InternetShortcut]\nURL=https://youtube.com/shorts/{SECOND}?si=x\n".encode("utf-16")
    )
    put_drop(tmp_path, FIRST_URL, ".hidden.txt")
    put_drop(tmp_path, FIRST_URL, "ignored.md")
    (tmp_path / "nested").mkdir()
    put_drop(tmp_path / "nested", "https://youtube.com/watch?v=abcdefghijk")

    videos, errors = inbox_app.scan_inbox(tmp_path)

    assert errors == []
    assert videos == [inbox_app.Video(FIRST, FIRST_URL), inbox_app.Video(SECOND, SECOND_URL)]


def test_markdown_share_links_extract_and_deduplicate():
    text = (
        f"[Watch this](https://youtu.be/{FIRST}?si=tracking)\n"
        f"<{FIRST_URL}&list=RDmix>\n"
        f"[Another video]({SECOND_URL})."
    )
    videos, errors = inbox_app.videos_from_text(text)
    assert errors == []
    assert videos == [inbox_app.Video(FIRST, FIRST_URL), inbox_app.Video(SECOND, SECOND_URL)]


def test_success_is_skipped_on_second_launch_even_with_a_different_share_link(tmp_path):
    put_drop(tmp_path, FIRST_URL)
    calls = []

    def processor(video, job):
        calls.append(video.video_id)
        write_artifact(video, job)

    status, paths = inbox_app.process_batch(tmp_path, processor=processor)
    assert status == 0
    assert len(paths) == 1 and paths[0].is_file()
    expected = paths[0].read_text()
    put_drop(tmp_path, f"https://youtu.be/{FIRST}?si=different&list=RD123", "another.txt")

    status, second_paths = inbox_app.process_batch(tmp_path, processor=processor)

    assert status == 0 and second_paths == []
    assert calls == [FIRST]
    assert paths[0].read_text() == expected
    registry = json.loads((tmp_path / ".processed.json").read_text())
    assert set(registry["completed"]) == {FIRST}
    assert registry["completed"][FIRST]["text_file"] == paths[0].name


def test_failed_video_stays_retryable_and_batch_continues(tmp_path):
    put_drop(tmp_path, f"{FIRST_URL}\n{SECOND_URL}\n")
    calls = []

    def fail_first(video, job):
        calls.append(video.video_id)
        if video.video_id == FIRST:
            raise RuntimeError("Download interrupted")
        write_artifact(video, job)

    status, paths = inbox_app.process_batch(tmp_path, processor=fail_first)
    assert status == 1 and len(paths) == 1
    assert calls == [FIRST, SECOND]
    registry = json.loads((tmp_path / ".processed.json").read_text())
    assert set(registry["completed"]) == {SECOND}

    def retry(video, job):
        calls.append(video.video_id)
        write_artifact(video, job)

    status, paths = inbox_app.process_batch(tmp_path, processor=retry)
    assert status == 0 and len(paths) == 1
    assert calls == [FIRST, SECOND, FIRST]
    assert set(json.loads((tmp_path / ".processed.json").read_text())["completed"]) == {FIRST, SECOND}


def test_silent_processor_failure_is_not_marked_completed(tmp_path):
    put_drop(tmp_path, FIRST_URL)
    status, paths = inbox_app.process_batch(tmp_path, processor=lambda video, job: None)
    assert status == 1 and paths == []
    assert not (tmp_path / ".processed.json").exists()


def test_deleted_export_restores_from_work_without_retranscribing(tmp_path):
    put_drop(tmp_path, FIRST_URL)
    status, paths = inbox_app.process_batch(tmp_path, processor=write_artifact)
    assert status == 0
    content = paths[0].read_bytes()
    paths[0].unlink()

    def must_not_transcribe(video, job):
        pytest.fail("Valid preserved artifact should be restored without transcription")

    status, restored = inbox_app.process_batch(tmp_path, processor=must_not_transcribe)
    assert status == 0 and restored == paths
    assert restored[0].read_bytes() == content


def test_non_utf8_export_restores_from_work_without_aborting_batch(tmp_path):
    put_drop(tmp_path, FIRST_URL)
    status, paths = inbox_app.process_batch(tmp_path, processor=write_artifact)
    assert status == 0
    content = paths[0].read_bytes()
    paths[0].write_bytes(b"\xff\xfe\x00\xd8broken")
    put_drop(tmp_path, SECOND_URL, "next.txt")
    calls = []

    def processor(video, job):
        calls.append(video.video_id)
        write_artifact(video, job)

    status, restored = inbox_app.process_batch(tmp_path, processor=processor)

    assert status == 0 and len(restored) == 2
    assert calls == [SECOND]
    assert paths[0].read_bytes() == content


def test_unreadable_export_restores_from_work(tmp_path, monkeypatch):
    put_drop(tmp_path, FIRST_URL)
    status, paths = inbox_app.process_batch(tmp_path, processor=write_artifact)
    assert status == 0
    exported = paths[0]
    content = exported.read_bytes()
    real_read_text = Path.read_text

    def unreadable_export(path, *args, **kwargs):
        if path == exported:
            raise OSError("The saved file cannot be read")
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", unreadable_export)

    def must_not_transcribe(video, job):
        pytest.fail("An unreadable export should be replaced using the preserved artifact")

    status, restored = inbox_app.process_batch(tmp_path, processor=must_not_transcribe)
    assert status == 0 and restored == paths
    assert exported.read_bytes() == content


def test_malformed_xml_webloc_reports_error_and_other_videos_continue(tmp_path, capsys):
    broken = tmp_path / "broken.webloc"
    broken.write_bytes(b'<?xml version="1.0"?><plist><dict><key>URL</key><string>https://youtu.be/')
    put_drop(tmp_path, FIRST_URL)
    calls = []

    def processor(video, job):
        calls.append(video.video_id)
        write_artifact(video, job)

    status, paths = inbox_app.process_batch(tmp_path, processor=processor)

    assert status == 1 and len(paths) == 1
    assert calls == [FIRST]
    assert "broken.webloc" in capsys.readouterr().err
    assert broken.read_bytes().endswith(b"https://youtu.be/")


@pytest.mark.parametrize("damage", ["truncated_text", "wrong_video", "empty_transcript", "invalid_json"])
def test_invalid_artifacts_are_preserved_before_retry(tmp_path, damage):
    put_drop(tmp_path, FIRST_URL)
    video = inbox_app.canonical_video(FIRST_URL)
    job = tmp_path / ".work" / FIRST
    txt = write_artifact(video, job)
    metadata = txt.with_suffix(".json")
    if damage == "truncated_text":
        txt.write_text("Transcript:\n--------------------\nOnly a partial sentence")
    elif damage == "invalid_json":
        metadata.write_text('{"transcript":')
    else:
        data = json.loads(metadata.read_text())
        if damage == "wrong_video":
            data["video_info"]["url"] = SECOND_URL
        else:
            data["transcript"] = ""
        metadata.write_text(json.dumps(data))
    old_txt, old_json = txt.read_bytes(), metadata.read_bytes()
    calls = []

    def retry(video, job):
        calls.append(video.video_id)
        assert not txt.exists() and not metadata.exists()
        recovery = list((job / ".incomplete").iterdir())
        assert len(recovery) == 1
        assert (recovery[0] / txt.name).read_bytes() == old_txt
        assert (recovery[0] / metadata.name).read_bytes() == old_json
        write_artifact(video, job)

    status, paths = inbox_app.process_batch(tmp_path, processor=retry)
    assert status == 0 and len(paths) == 1 and calls == [FIRST]


@pytest.mark.parametrize("registry", [
    '{"completed":',
    '{"version": 2, "completed": {}}',
    '{"version": 1, "completed": []}',
    '{"version": 1, "completed": {"not-a-video-id": {}}}',
])
def test_corrupt_history_blocks_processing_without_overwriting_history(tmp_path, registry):
    put_drop(tmp_path, FIRST_URL)
    history = tmp_path / ".processed.json"
    history.write_text(registry)

    def must_not_transcribe(video, job):
        pytest.fail("Corrupt history must stop processing")

    with pytest.raises(RuntimeError, match="Cannot read processing history"):
        inbox_app.process_batch(tmp_path, processor=must_not_transcribe)
    assert history.read_text() == registry
    assert not (tmp_path / ".work").exists()


def test_second_processing_lock_is_rejected_then_reusable(tmp_path):
    with inbox_app.processing_lock(tmp_path):
        with pytest.raises(RuntimeError, match="already processing"):
            with inbox_app.processing_lock(tmp_path):
                pytest.fail("Concurrent processing lock unexpectedly acquired")
    with inbox_app.processing_lock(tmp_path):
        pass


def test_graph_state_enforces_requested_workflow_and_isolates_job_output(tmp_path):
    video = inbox_app.canonical_video(f"{FIRST_URL}&list=RDmix")
    state = inbox_app.graph_state(video, tmp_path, stt="whisper-turbo")
    assert state["url"] == FIRST_URL
    assert state["video_urls"] == [(FIRST_URL, "unknown")]
    assert state["output_dir"] == str(tmp_path.resolve())
    assert state["is_playlist"] is False
    assert state["audio_only"] is False
    assert state["save_video"] is False
    assert state["is_local_file"] is False
    assert state["reference_audio_path"] is None
    assert state["transcription_backend"] == "whisper"
    assert state["stt_model"] == "whisper-turbo"
    assert state["current_index"] == 0
    assert state["video_transcripts"] == []


def test_graph_state_parakeet_uses_feature_path(tmp_path):
    video = inbox_app.canonical_video(FIRST_URL)
    state = inbox_app.graph_state(video, tmp_path, stt="parakeet")
    assert state["stt_model"] == "parakeet"
    assert state["transcription_backend"] == "whisper"


def test_graph_state_voxtral_skips_feature_path(tmp_path):
    video = inbox_app.canonical_video(FIRST_URL)
    state = inbox_app.graph_state(video, tmp_path, stt="voxtral")
    assert state["stt_model"] == "voxtral"
    assert state["transcription_backend"] == "voxtral"


def test_dry_run_never_loads_processor_or_creates_processing_history(tmp_path):
    put_drop(tmp_path, FIRST_URL)

    def must_not_transcribe(video, job):
        pytest.fail("Dry run must not transcribe")

    status, paths = inbox_app.process_batch(tmp_path, dry_run=True, processor=must_not_transcribe)
    assert status == 0 and paths == []
    assert not (tmp_path / ".processed.json").exists()
    assert not (tmp_path / ".work").exists()
