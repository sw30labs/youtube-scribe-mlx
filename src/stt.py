#!/usr/bin/env python3
"""Selectable local STT backends (MLX / Metal).

The previous default, Whisper large-v3-turbo, remains available. Parakeet TDT
0.6B v3 is the recommended default for English and other European languages.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence


ENV_VAR = "STT_MODEL"
CONFIG_NAME = ".stt.json"
GLOBAL_CONFIG = Path.home() / ".config" / "mlx-youtube-scribe" / "stt.json"
SAMPLE_RATE = 16_000
DEFAULT_STT = "parakeet"


@dataclass(frozen=True)
class SttChoice:
    key: str
    label: str
    app_label: str
    backend: str
    model_id: str
    languages: str
    chunk_duration: Optional[float] = None
    overlap_duration: Optional[float] = None
    language_style: str = "code"


STT_CHOICES: dict[str, SttChoice] = {
    "parakeet": SttChoice(
        key="parakeet",
        label="Parakeet TDT 0.6B v3",
        app_label="Parakeet TDT 0.6B v3 — recommended (NVIDIA, EN/EU)",
        backend="mlx-audio",
        model_id="mlx-community/parakeet-tdt-0.6b-v3",
        languages="English + 24 other European languages",
        chunk_duration=120.0,
        overlap_duration=15.0,
        language_style="none",
    ),
    "whisper-turbo": SttChoice(
        key="whisper-turbo",
        label="Whisper large-v3-turbo",
        app_label="Whisper large-v3-turbo — previous default (99 languages)",
        backend="whisper",
        model_id="mlx-community/whisper-large-v3-turbo",
        languages="99+ languages",
        language_style="code",
    ),
    "whisper-large": SttChoice(
        key="whisper-large",
        label="Whisper large-v3",
        app_label="Whisper large-v3 — higher quality Whisper (slower)",
        backend="whisper",
        model_id="mlx-community/whisper-large-v3-mlx",
        languages="99+ languages",
        language_style="code",
    ),
    "qwen3-asr": SttChoice(
        key="qwen3-asr",
        label="Qwen3-ASR 1.7B",
        app_label="Qwen3-ASR 1.7B — multilingual / CJK / songs",
        backend="mlx-audio",
        model_id="mlx-community/Qwen3-ASR-1.7B-8bit",
        languages="Multilingual, strong CJK and code-switch",
        chunk_duration=600.0,
        language_style="name",
    ),
    "voxtral": SttChoice(
        key="voxtral",
        label="Voxtral Mini 3B",
        app_label="Voxtral Mini 3B — existing audio-LLM STT",
        backend="voxtral",
        model_id="mistralai/Voxtral-Mini-3B-2507",
        languages="Multiple",
        language_style="code",
    ),
}

APP_LABELS = {choice.app_label: choice.key for choice in STT_CHOICES.values()}
_ALIASES = {
    "whisper": "whisper-turbo",
    "turbo": "whisper-turbo",
    "large-v3-turbo": "whisper-turbo",
    "large-v3": "whisper-large",
    "whisper-large-v3": "whisper-large",
    "qwen": "qwen3-asr",
    "qwen3": "qwen3-asr",
}


def _read_config(path: Path) -> Optional[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("stt")
    return value if isinstance(value, str) else None


def config_path(inbox: Optional[os.PathLike[str] | str] = None) -> Path:
    override = os.environ.get("STT_CONFIG")
    if override:
        return Path(override).expanduser()
    if inbox is not None:
        return Path(inbox).expanduser() / CONFIG_NAME
    return GLOBAL_CONFIG


def normalize_stt_key(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    key = _ALIASES.get(raw.lower(), raw.lower())
    if key in STT_CHOICES:
        return key
    raise ValueError(
        f"Unknown STT '{value}'. Choose one of: {', '.join(STT_CHOICES)}"
    )


def resolve_stt_key(
    explicit: Optional[str] = None,
    *,
    inbox: Optional[os.PathLike[str] | str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> str:
    env = os.environ if environ is None else environ
    if explicit is not None and str(explicit).strip():
        return normalize_stt_key(str(explicit)) or DEFAULT_STT
    candidates = [
        env.get(ENV_VAR),
        _read_config(config_path(inbox)) if inbox is not None else None,
        _read_config(GLOBAL_CONFIG),
        DEFAULT_STT,
    ]
    for candidate in candidates:
        if candidate is None or not str(candidate).strip():
            continue
        try:
            return normalize_stt_key(str(candidate)) or DEFAULT_STT
        except ValueError:
            continue
    return DEFAULT_STT


def resolve_choice(
    explicit: Optional[str] = None,
    *,
    inbox: Optional[os.PathLike[str] | str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> SttChoice:
    return STT_CHOICES[resolve_stt_key(explicit, inbox=inbox, environ=environ)]


def graph_backend(choice: SttChoice) -> str:
    return "voxtral" if choice.backend == "voxtral" else "whisper"


def save_stt(
    key: str,
    *,
    inbox: Optional[os.PathLike[str] | str] = None,
) -> SttChoice:
    choice = STT_CHOICES[normalize_stt_key(key) or DEFAULT_STT]
    payload = json.dumps({"stt": choice.key}, indent=2) + "\n"
    targets = [GLOBAL_CONFIG]
    if inbox is not None:
        targets.append(config_path(inbox))
    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
    return choice


def app_labels() -> list[str]:
    return [choice.app_label for choice in STT_CHOICES.values()]


def default_app_label(
    *,
    inbox: Optional[os.PathLike[str] | str] = None,
) -> str:
    return resolve_choice(inbox=inbox).app_label


def key_from_app_label(label: str) -> str:
    key = APP_LABELS.get(label.strip())
    if key is None:
        raise ValueError(f"Unknown STT label: {label}")
    return key


def add_stt_argument(parser: argparse.ArgumentParser) -> None:
    keys = ", ".join(STT_CHOICES)
    parser.add_argument(
        "--stt",
        default=None,
        metavar="MODEL",
        help=(
            "Speech-to-text model: "
            f"{keys}. Default is the saved selection "
            f"(built-in: {DEFAULT_STT}). Also reads ${ENV_VAR}."
        ),
    )
    parser.add_argument(
        "--save-stt",
        action="store_true",
        help="Remember --stt as the default for later runs",
    )


def prompt_stt(default_key: Optional[str] = None) -> str:
    default = resolve_stt_key(default_key)
    print("\nSpeech-to-text model:")
    for index, choice in enumerate(STT_CHOICES.values(), 1):
        marker = " (default)" if choice.key == default else ""
        print(f"  ({index}) {choice.label}{marker} — {choice.languages}")
    raw = input(f"STT [{default}]: ").strip()
    if not raw:
        return default
    if raw.isdigit():
        items = list(STT_CHOICES)
        position = int(raw)
        if 1 <= position <= len(items):
            return items[position - 1]
        raise ValueError(f"STT choice must be 1–{len(items)}")
    return normalize_stt_key(raw) or default


def get_transcriber(
    stt: Optional[str] = None,
    *,
    language: str = "en",
    inbox: Optional[os.PathLike[str] | str] = None,
) -> Any:
    choice = resolve_choice(stt, inbox=inbox)
    try:
        return _make_transcriber(choice, language=language)
    except ImportError as exc:
        if choice.key == "whisper-turbo":
            raise
        print(
            f"STT '{choice.key}' is unavailable ({exc}). "
            "Falling back to whisper-turbo.",
            file=sys.stderr,
        )
        return _make_transcriber(STT_CHOICES["whisper-turbo"], language=language)


def _make_transcriber(choice: SttChoice, *, language: str) -> Any:
    if choice.backend == "whisper":
        from whisper_mlx import AudioTranscriber

        return AudioTranscriber.get_instance(
            language=language, model_id=choice.model_id
        )
    if choice.backend == "mlx-audio":
        from mlx_audio_stt import MlxAudioTranscriber

        return MlxAudioTranscriber.get_instance(choice, language=language)
    if choice.backend == "voxtral":
        from voxtral_mlx import VoxtralTranscriber

        return VoxtralTranscriber.get_instance()
    raise ValueError(f"Unsupported STT backend: {choice.backend}")


def cleanup_all() -> None:
    try:
        from whisper_mlx import AudioTranscriber

        AudioTranscriber.cleanup_singleton()
    except Exception:
        pass
    try:
        from mlx_audio_stt import MlxAudioTranscriber

        MlxAudioTranscriber.cleanup_singleton()
    except Exception:
        pass
    try:
        from voxtral_mlx import VoxtralTranscriber

        VoxtralTranscriber.cleanup()
    except Exception:
        pass


def _cli(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-dialog-data", action="store_true")
    parser.add_argument("--save-from-label", metavar="LABEL")
    parser.add_argument("--inbox", type=Path, default=None)
    parser.add_argument("--print-default", action="store_true")
    args = parser.parse_args(argv)
    inbox = args.inbox
    if args.app_dialog_data:
        print(default_app_label(inbox=inbox))
        for label in app_labels():
            print(label)
        return 0
    if args.save_from_label:
        choice = save_stt(key_from_app_label(args.save_from_label), inbox=inbox)
        print(choice.key)
        return 0
    if args.print_default:
        print(resolve_stt_key(inbox=inbox))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli())
