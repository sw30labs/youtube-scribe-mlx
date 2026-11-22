#!/usr/bin/env python3
"""mlx-audio STT backends: Parakeet, Qwen3-ASR, Nemotron, and other Metal models."""

from __future__ import annotations

import gc
import inspect
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Union

import numpy as np

from stt import SAMPLE_RATE, SttChoice

# Nemotron 3.5 Transcribe encodes a whole recording (up to one hour).
NEMOTRON_MAX_SECONDS = 3600
# BF16 weights are about 66 GB. Leave headroom for the audio encoder and KV cache.
NEMOTRON_BF16_GB = 80


AudioInput = Union[str, os.PathLike, np.ndarray]

_LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "nl": "Dutch",
    "pl": "Polish",
    "sv": "Swedish",
    "uk": "Ukrainian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
}


def _import_mlx_audio_stt(choice: Optional[SttChoice] = None):
    try:
        import mlx.core as mx
        from mlx_audio.stt import load
    except ImportError as exc:
        missing = getattr(exc, "name", None) or "mlx-audio"
        raise ImportError(
            f"Missing dependency '{missing}'. Install local STT deps with: "
            "pip install mlx-audio"
        ) from exc
    if choice is not None and choice.key == "nemotron":
        try:
            import mlx_audio.stt.models.nemotron_transcribe  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "Nemotron 3.5 Transcribe needs mlx-audio>=0.6.3 "
                "(model type nemo_speechlm). Upgrade with: "
                "pip install -U 'mlx-audio>=0.6.3'"
            ) from exc
    return mx, load


def _available_memory_gb() -> Optional[float]:
    """Reclaimable macOS memory from vm_stat. None when that cannot be read."""
    try:
        raw = subprocess.check_output(["vm_stat"], text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = raw.splitlines()
    if not lines:
        return None
    page = 4096
    header = lines[0]
    if "page size of" in header:
        try:
            page = int(header.split("page size of", 1)[1].split()[0])
        except (IndexError, ValueError):
            page = 4096
    counts: dict[str, int] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits:
            counts[key.strip()] = int(digits)
    pages = sum(
        counts.get(name, 0)
        for name in ("Pages free", "Pages inactive", "Pages speculative")
    )
    return pages * page / (1024 ** 3)


def _warn_nemotron_memory(model_id: str) -> None:
    quantized = any(
        tag in model_id.lower()
        for tag in ("4bit", "4-bit", "8bit", "8-bit", "mxfp", "nvfp")
    )
    available = _available_memory_gb()
    need = 28 if quantized else NEMOTRON_BF16_GB
    if available is None:
        print(
            f"Loading {model_id}. The BF16 checkpoint is about 66 GB. "
            "Unload other large models first.",
            file=sys.stderr,
        )
        return
    print(
        f"About {available:.0f} GB reclaimable before loading {model_id}.",
        file=sys.stderr,
    )
    if available < need:
        print(
            f"Warning: reclaimable memory ({available:.0f} GB) is under ~{need} GB. "
            "Unload other large models, or set NEMOTRON_STT_MODEL to a 4-bit MLX "
            "build such as nativ-community/Nemotron-3.5-Transcribe-30B-A4B-EA-4bit.",
            file=sys.stderr,
        )


def _clear_mlx_cache() -> None:
    try:
        import mlx.core as mx
    except ImportError:
        return
    if hasattr(mx, "clear_cache"):
        mx.clear_cache()


def _as_audio_input(audio: AudioInput, mx):
    if isinstance(audio, (str, os.PathLike, Path)):
        return os.fspath(audio)
    if isinstance(audio, np.ndarray):
        array = np.ascontiguousarray(audio, dtype=np.float32)
    else:
        array = np.asarray(audio, dtype=np.float32)
    if array.ndim > 1:
        array = np.mean(array, axis=1 if array.shape[-1] <= 8 else 0)
    return mx.array(np.ascontiguousarray(array, dtype=np.float32))


def _language_argument(style: str, language: str) -> Optional[str]:
    if style == "none" or not language:
        return None
    if style == "name":
        if len(language) > 3:
            return language
        return _LANGUAGE_NAMES.get(language.lower(), language)
    return language


class MlxAudioTranscriber:
    """Load one mlx-audio STT model and transcribe files or 16 kHz waveforms."""

    _instance: Optional["MlxAudioTranscriber"] = None

    def __init__(self, choice: SttChoice, language: str = "en") -> None:
        self.choice = choice
        self.model_id = choice.model_id
        self.language = language
        mx, load = _import_mlx_audio_stt(choice)
        if choice.key == "nemotron":
            _warn_nemotron_memory(choice.model_id)
        print(
            f"Loading mlx-audio STT '{choice.label}' ({choice.model_id}) "
            "on Apple GPU (Metal)...",
            file=sys.stderr,
        )
        self.model = load(choice.model_id)
        self._mx = mx
        print(f"mlx-audio STT ready: {choice.label}.", file=sys.stderr)

    @classmethod
    def get_instance(
        cls, choice: SttChoice, language: str = "en"
    ) -> "MlxAudioTranscriber":
        current = cls._instance
        if current is not None and (
            current.model_id != choice.model_id or current.language != language
        ):
            current.cleanup()
        if cls._instance is None:
            cls._instance = cls(choice, language=language)
        return cls._instance

    def transcribe(
        self,
        audio: AudioInput,
        *,
        verbose: Optional[bool] = None,
    ) -> str:
        if self.choice.key == "nemotron" and isinstance(audio, np.ndarray):
            seconds = int(np.asarray(audio).shape[0]) / SAMPLE_RATE
            if seconds > NEMOTRON_MAX_SECONDS:
                raise ValueError(
                    "Nemotron 3.5 Transcribe accepts recordings up to "
                    f"{NEMOTRON_MAX_SECONDS // 60} minutes; this audio is "
                    f"{seconds / 60:.1f} minutes."
                )
        prepared = _as_audio_input(audio, self._mx)
        kwargs: dict = {}
        language = _language_argument(self.choice.language_style, self.language)
        if language is not None:
            kwargs["language"] = language
        if self.choice.chunk_duration is not None:
            kwargs["chunk_duration"] = self.choice.chunk_duration
        if self.choice.overlap_duration is not None:
            kwargs["overlap_duration"] = self.choice.overlap_duration
        if self.choice.max_tokens is not None:
            kwargs["max_tokens"] = self.choice.max_tokens
        if self.choice.task is not None:
            kwargs["task"] = self.choice.task
        if verbose is not None:
            kwargs["verbose"] = verbose
        signature = inspect.signature(self.model.generate)
        kwargs = {key: value for key, value in kwargs.items() if key in signature.parameters}
        result = self.model.generate(prepared, **kwargs)
        return (getattr(result, "text", None) or "").strip()

    def cleanup(self) -> None:
        self.model = None
        gc.collect()
        _clear_mlx_cache()
        if MlxAudioTranscriber._instance is self:
            MlxAudioTranscriber._instance = None

    @classmethod
    def cleanup_singleton(cls) -> None:
        if cls._instance is not None:
            cls._instance.cleanup()
        else:
            _clear_mlx_cache()
