import json
import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import stt


class SttCatalogTests(unittest.TestCase):
    def test_keeps_whisper_turbo_and_recommends_parakeet(self):
        self.assertEqual(stt.DEFAULT_STT, "parakeet")
        self.assertIn("whisper-turbo", stt.STT_CHOICES)
        self.assertEqual(
            stt.STT_CHOICES["whisper-turbo"].model_id,
            "mlx-community/whisper-large-v3-turbo",
        )
        self.assertEqual(
            stt.STT_CHOICES["parakeet"].model_id,
            "mlx-community/parakeet-tdt-0.6b-v3",
        )
        self.assertEqual(
            stt.STT_CHOICES["whisper-large"].model_id,
            "mlx-community/whisper-large-v3-mlx",
        )

    def test_aliases_and_rejects_unknown(self):
        self.assertEqual(stt.normalize_stt_key("whisper"), "whisper-turbo")
        self.assertEqual(stt.normalize_stt_key("Qwen3"), "qwen3-asr")
        with self.assertRaisesRegex(ValueError, "Unknown STT"):
            stt.normalize_stt_key("not-a-model")

    def test_explicit_choice_beats_env_and_saved_config(self):
        with self.assertRaisesRegex(ValueError, "Unknown STT"):
            stt.resolve_stt_key("nope", environ={"STT_MODEL": "whisper-turbo"})
        self.assertEqual(
            stt.resolve_stt_key("whisper-large", environ={"STT_MODEL": "parakeet"}),
            "whisper-large",
        )

    def test_env_beats_saved_config(self):
        self.assertEqual(
            stt.resolve_stt_key(environ={"STT_MODEL": "qwen3-asr"}),
            "qwen3-asr",
        )

    def test_saved_inbox_config_and_global_fallback(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            inbox = Path(temp_dir) / "inbox"
            inbox.mkdir()
            global_path = Path(temp_dir) / "global.json"
            global_path.write_text(json.dumps({"stt": "whisper-large"}), encoding="utf-8")
            (inbox / ".stt.json").write_text(
                json.dumps({"stt": "whisper-turbo"}), encoding="utf-8"
            )
            with mock.patch.object(stt, "GLOBAL_CONFIG", global_path):
                self.assertEqual(stt.resolve_stt_key(inbox=inbox, environ={}), "whisper-turbo")
                self.assertEqual(stt.resolve_stt_key(environ={}), "whisper-large")

    def test_save_stt_writes_inbox_and_global(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            inbox = Path(temp_dir) / "inbox"
            global_path = Path(temp_dir) / "cfg" / "stt.json"
            with mock.patch.object(stt, "GLOBAL_CONFIG", global_path):
                choice = stt.save_stt("whisper-turbo", inbox=inbox)
            self.assertEqual(choice.key, "whisper-turbo")
            self.assertEqual(json.loads(global_path.read_text())["stt"], "whisper-turbo")
            self.assertEqual(
                json.loads((inbox / ".stt.json").read_text())["stt"],
                "whisper-turbo",
            )

    def test_graph_backend_only_voxtral_skips_features(self):
        self.assertEqual(stt.graph_backend(stt.STT_CHOICES["parakeet"]), "whisper")
        self.assertEqual(stt.graph_backend(stt.STT_CHOICES["whisper-turbo"]), "whisper")
        self.assertEqual(stt.graph_backend(stt.STT_CHOICES["voxtral"]), "voxtral")

    def test_app_dialog_data_starts_with_current_default(self):
        import io
        from contextlib import redirect_stdout

        stdout = io.StringIO()
        with mock.patch.object(stt, "GLOBAL_CONFIG", Path("/tmp/missing-stt.json")):
            with redirect_stdout(stdout):
                code = stt._cli(["--app-dialog-data"])
        self.assertEqual(code, 0)
        lines = stdout.getvalue().splitlines()
        self.assertEqual(lines[0], stt.STT_CHOICES["parakeet"].app_label)
        self.assertEqual(lines[1:], stt.app_labels())

    def test_save_from_label(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            inbox = Path(temp_dir)
            global_path = Path(temp_dir) / "global.json"
            stdout = __import__("io").StringIO()
            with mock.patch.object(stt, "GLOBAL_CONFIG", global_path):
                with __import__("contextlib").redirect_stdout(stdout):
                    code = stt._cli(
                        [
                            "--save-from-label",
                            stt.STT_CHOICES["whisper-large"].app_label,
                            "--inbox",
                            str(inbox),
                        ]
                    )
            self.assertEqual(code, 0)
            self.assertEqual(stdout.getvalue().strip(), "whisper-large")


class GetTranscriberTests(unittest.TestCase):
    def test_whisper_factory_passes_model_id(self):
        fake = mock.Mock()
        with mock.patch("whisper_mlx.AudioTranscriber.get_instance", return_value=fake) as get_instance:
            transcriber = stt.get_transcriber("whisper-large", language="es")
        get_instance.assert_called_once_with(
            language="es",
            model_id="mlx-community/whisper-large-v3-mlx",
        )
        self.assertIs(transcriber, fake)

    def test_falls_back_to_whisper_turbo_when_mlx_audio_missing(self):
        fake = mock.Mock()
        with mock.patch.object(
            stt,
            "_make_transcriber",
            side_effect=[ImportError("mlx-audio"), fake],
        ) as make:
            transcriber = stt.get_transcriber("parakeet")
        self.assertIs(transcriber, fake)
        self.assertEqual(make.call_args_list[0].args[0].key, "parakeet")
        self.assertEqual(make.call_args_list[1].args[0].key, "whisper-turbo")


if __name__ == "__main__":
    unittest.main()
