import numpy as np

from src.constants import SAMPLE_RATE, VOLUME
from src.tts.player import TtsPlayer


class FakeStream:
    def __init__(self):
        self.active = False
        self.writes = []

    def start(self):
        self.active = True

    def stop(self):
        self.active = False

    def write(self, block):
        self.writes.append(np.asarray(block))


def _noop_pipeline(_text, **_kwargs):
    if False:
        yield None


def test_to_float32_clips_and_converts():
    player = TtsPlayer(_noop_pipeline)
    result = player._to_float32([2.0, -2.0, 0.5])
    assert result.dtype == np.float32
    expected = np.array([2.0, -2.0, 0.5], dtype=np.float32) * VOLUME
    expected = np.clip(expected, -1.0, 1.0)
    assert np.allclose(result, expected)


def test_to_float32_none_returns_silence():
    player = TtsPlayer(_noop_pipeline)
    result = player._to_float32(None)
    assert result.dtype == np.float32
    assert result.shape == (1,)
    assert result[0] == 0.0


def test_ms_sample_roundtrip():
    player = TtsPlayer(_noop_pipeline)
    assert player._ms_to_samples(1000) == SAMPLE_RATE
    assert player._samples_to_ms(SAMPLE_RATE) == 1000


def test_play_segment_writes_all_samples_and_updates_offsets():
    player = TtsPlayer(_noop_pipeline)
    stream = FakeStream()
    stream.start()
    segment = np.linspace(-0.5, 0.5, 5000, dtype=np.float32)

    player.resume_event.set()
    player.stop_event.clear()
    player.offset_samples = 0
    player.offset_ms = 0

    stopped = player._play_segment(segment, stream)

    assert stopped is False
    assert player.offset_samples == len(segment)
    assert player.offset_ms == player._samples_to_ms(len(segment))
    assert sum(block.size for block in stream.writes) == len(segment)


def test_pause_resume_toggles_flags_and_events():
    player = TtsPlayer(_noop_pipeline)
    player.is_playing = True
    player.is_paused = False
    player.resume_event.set()

    player.pause()
    assert player.is_paused is True
    assert player.resume_event.is_set() is False

    player.resume()
    assert player.is_paused is False
    assert player.resume_event.is_set() is True


def test_stop_resets_state():
    player = TtsPlayer(_noop_pipeline)
    player.is_playing = True
    player.is_paused = True
    player.offset_ms = 123
    player.offset_samples = 456
    player.text = "hello"

    player.stop()

    assert player.is_playing is False
    assert player.is_paused is False
    assert player.offset_ms == 0
    assert player.offset_samples == 0
    assert player.text == ""
    assert player.stop_event.is_set() is True
