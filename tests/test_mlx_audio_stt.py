import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import mlx_audio_stt
import stt


class FakeModel:
    def __init__(self):
        self.calls = []

    def generate(self, audio, chunk_duration=None, overlap_duration=None,
                 verbose=None, language=None):
        self.calls.append(
            {
                "audio": audio,
                "chunk_duration": chunk_duration,
                "overlap_duration": overlap_duration,
                "verbose": verbose,
                "language": language,
            }
        )
        return types.SimpleNamespace(text="  hello parakeet  ")


class MlxAudioTranscriberTests(unittest.TestCase):
    def tearDown(self):
        mlx_audio_stt.MlxAudioTranscriber._instance = None

    def test_parakeet_chunks_long_audio_and_converts_numpy(self):
        model = FakeModel()
        fake_mx = types.SimpleNamespace(
            array=lambda data: ("mx", tuple(np.asarray(data).shape), str(np.asarray(data).dtype))
        )
        with mock.patch.object(
            mlx_audio_stt,
            "_import_mlx_audio_stt",
            return_value=(fake_mx, mock.Mock(return_value=model)),
        ):
            transcriber = mlx_audio_stt.MlxAudioTranscriber(
                stt.STT_CHOICES["parakeet"], language="en"
            )
            text = transcriber.transcribe(np.zeros(8, dtype=np.float32), verbose=False)

        call = model.calls[0]
        self.assertEqual(call["chunk_duration"], 120.0)
        self.assertEqual(call["overlap_duration"], 15.0)
        self.assertFalse(call["verbose"])
        self.assertIsNone(call["language"])
        self.assertEqual(call["audio"][0], "mx")
        self.assertEqual(text, "hello parakeet")

    def test_qwen3_maps_language_code_to_name(self):
        model = FakeModel()
        fake_mx = types.SimpleNamespace(array=lambda data: data)
        with mock.patch.object(
            mlx_audio_stt,
            "_import_mlx_audio_stt",
            return_value=(fake_mx, mock.Mock(return_value=model)),
        ):
            transcriber = mlx_audio_stt.MlxAudioTranscriber(
                stt.STT_CHOICES["qwen3-asr"], language="en"
            )
            transcriber.transcribe("/tmp/a.wav")

        call = model.calls[0]
        self.assertEqual(call["language"], "English")
        self.assertEqual(call["chunk_duration"], 600.0)
        self.assertEqual(call["audio"], "/tmp/a.wav")
