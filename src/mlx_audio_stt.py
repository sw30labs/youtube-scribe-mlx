#!/usr/bin/env python3
"""mlx-audio STT backends: Parakeet, Qwen3-ASR, and other Metal models."""

from __future__ import annotations

import gc
import inspect
import os
import sys
from pathlib import Path
from typing import Optional, Union

import numpy as np

from stt import SttChoice


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


def _import_mlx_audio_stt():
    try:
        import mlx.core as mx
        from mlx_audio.stt import load
    except ImportError as exc:
        missing = getattr(exc, "name", None) or "mlx-audio"
        raise ImportError(
            f"Missing dependency '{missing}'. Install local STT deps with: "
            "pip install mlx-audio"
        ) from exc
    return mx, load


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
        mx, load = _import_mlx_audio_stt()
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
        prepared = _as_audio_input(audio, self._mx)
        kwargs: dict = {}
        language = _language_argument(self.choice.language_style, self.language)
        if language is not None:
            kwargs["language"] = language
        if self.choice.chunk_duration is not None:
            kwargs["chunk_duration"] = self.choice.chunk_duration
        if self.choice.overlap_duration is not None:
            kwargs["overlap_duration"] = self.choice.overlap_duration
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
