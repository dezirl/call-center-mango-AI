import os
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault("VOICEBRIDGE_DISABLE_STARTUP_WARMUPS", "1")

import app as voicebridge


class FakeCallAudio:
    def __init__(self, samples):
        self.samples = iter(samples)
        self.played = []

    def play_wav(self, wav_bytes, requested=""):
        self.played.append((wav_bytes, requested))

    def capture_speech(self, **_kwargs):
        return next(self.samples)


class CallHearingCheckTests(unittest.TestCase):
    def make_service(self, samples):
        service = voicebridge.MangoCallService.__new__(voicebridge.MangoCallService)
        service.audio = FakeCallAudio(samples)
        service._stop = threading.Event()
        service._lock = threading.RLock()
        service._status = {}
        return service

    def check(self, service, transcripts):
        with (
            patch.object(voicebridge.silero_tts_service, "synthesize_script", return_value=b"wav") as synthesize,
            patch.object(voicebridge.MangoCallService, "_transcribe_chunk", side_effect=transcripts),
        ):
            result = service._confirm_remote_hearing({}, "speaker", "ru", 1.0, "xenia")
        return result, synthesize

    def test_silence_gets_one_followup_then_confirmed_reply_proceeds(self):
        service = self.make_service([b"", b"candidate voice"])
        result, synthesize = self.check(service, ["Да, я вас слышу"])
        self.assertEqual(result, ("Да, я вас слышу", "", False))
        self.assertEqual(synthesize.call_count, 2)
        self.assertEqual(len(service.audio.played), 2)

    def test_silence_after_both_prompts_does_not_confirm_hearing(self):
        service = self.make_service([b"", b""])
        result, synthesize = self.check(service, [])
        self.assertEqual(result, ("", "", False))
        self.assertEqual(synthesize.call_count, 2)

    def test_exact_loopback_echo_is_not_a_candidate_reply(self):
        service = self.make_service([b"echo", b"candidate voice"])
        result, synthesize = self.check(
            service,
            [voicebridge.MANGO_HEARING_CHECK, "Да, слышу"],
        )
        self.assertEqual(result, ("Да, слышу", "", False))
        self.assertEqual(synthesize.call_count, 2)

    def test_autoanswer_during_check_is_returned_for_hangup(self):
        service = self.make_service([b"automated voice", b""])
        result, synthesize = self.check(service, ["Оставьте сообщение после сигнала"])
        self.assertEqual(result[0], "Оставьте сообщение после сигнала")
        self.assertEqual(result[1], "оставьте сообщение")
        self.assertFalse(result[2])
        self.assertEqual(synthesize.call_count, 1)

    def test_stt_failure_is_reported_as_unverified(self):
        service = self.make_service([b"voice"])
        result, _synthesize = self.check(service, [RuntimeError("STT offline")])
        self.assertEqual(result, ("", "", True))


if __name__ == "__main__":
    unittest.main()
