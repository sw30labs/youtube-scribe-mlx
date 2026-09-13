#!/usr/bin/env python3
"""Voxtral Mini transcription via mlx-voxtral."""

from __future__ import annotations

import gc
from typing import Optional


MODEL_ID = "mistralai/Voxtral-Mini-3B-2507"


class VoxtralTranscriber:
    """Audio transcription using Voxtral-Mini-3B via mlx-voxtral (singleton)."""

    _instance: Optional["VoxtralTranscriber"] = None
    prefers_path = True

    def __init__(self, model_id: str = MODEL_ID) -> None:
        from mlx_voxtral import VoxtralForConditionalGeneration, VoxtralProcessor

        self.model_id = model_id
        print(f"Loading Voxtral model: {model_id}...")
        self.model = VoxtralForConditionalGeneration.from_pretrained(model_id)
        self.processor = VoxtralProcessor.from_pretrained(model_id)
        print("Voxtral model loaded!")

    @classmethod
    def get_instance(cls, model_id: str = MODEL_ID) -> "VoxtralTranscriber":
        if cls._instance is not None and cls._instance.model_id != model_id:
            cls.cleanup()
        if cls._instance is None:
            cls._instance = cls(model_id=model_id)
        return cls._instance

    @classmethod
    def cleanup(cls) -> None:
        if cls._instance is not None:
            del cls._instance.model
            del cls._instance.processor
            cls._instance = None
            gc.collect()

    def transcribe(self, audio_path: str, *, verbose: Optional[bool] = None) -> str:
        del verbose
        try:
            inputs = self.processor.apply_transcrition_request(
                audio=audio_path,
                language="en",
            )
            outputs = self.model.generate(
                input_ids=inputs.input_ids,
                input_features=inputs.input_features,
                max_new_tokens=4096,
                temperature=0.0,
            )
            return self.processor.decode(
                outputs[0][inputs.input_ids.shape[1]:],
                skip_special_tokens=True,
            ).strip()
        except Exception as exc:
            print(f"Error in Voxtral transcription: {exc}")
            return ""
