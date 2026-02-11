import queue
import threading
import time

import numpy as np
import sounddevice as sd

from .constants import BLOCK_SIZE, SAMPLE_RATE, SPEED, VOICE


class TtsPlayer:
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.text = ""
        self.play_thread = None
        self.play_lock = threading.Lock()
        self.is_playing = False
        self.is_paused = False
        self.offset_ms = 0
        self.offset_samples = 0
        self.start_time = 0.0
        self.current_segment_start_samples = 0
        self.current_segment_len_samples = 0
        self.stop_event = threading.Event()
        self.resume_event = threading.Event()
        self.resume_event.set()
        self.on_state = None

    def _notify_state(self):
        if self.on_state:
            self.on_state()

    def load_text(self, text):
        self.stop()
        self.text = text
        self.offset_ms = 0
        self.offset_samples = 0

    def _chunk_segments(self, text):
        for _, _, audio in self.pipeline(text, voice=VOICE, speed=SPEED, split_pattern=r"\n+"):
            yield self._to_float32(audio)

    def _produce_segments(self, text, out_queue):
        try:
            for segment in self._chunk_segments(text):
                while not self.stop_event.is_set():
                    try:
                        out_queue.put(segment, timeout=0.1)
                        break
                    except queue.Full:
                        continue
                if self.stop_event.is_set():
                    break
        finally:
            try:
                out_queue.put_nowait(None)
            except queue.Full:
                pass

    @staticmethod
    def _to_float32(audio):
        if audio is None:
            return np.zeros(1, dtype=np.float32)
        audio = np.asarray(audio, dtype=np.float32)
        return np.clip(audio, -1.0, 1.0)

    @staticmethod
    def _ms_to_samples(ms):
        return int(ms * SAMPLE_RATE / 1000)

    @staticmethod
    def _samples_to_ms(samples):
        return int(samples * 1000 / SAMPLE_RATE)

    def play(self):
        with self.play_lock:
            if not self.text or self.is_playing:
                return
            self.offset_samples = self._ms_to_samples(self.offset_ms)
            self.stop_event.clear()
            self.resume_event.set()
            self.is_playing = True
            self.is_paused = False
            self.play_thread = threading.Thread(target=self._play_worker, daemon=True)
            self.play_thread.start()
        self._notify_state()

    def _play_worker(self):
        skip_samples = self.offset_samples
        segment_queue = queue.Queue(maxsize=4)
        producer = threading.Thread(
            target=self._produce_segments,
            args=(self.text, segment_queue),
            daemon=True,
        )
        producer.start()
        stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=BLOCK_SIZE,
        )
        stream.start()
        try:
            while True:
                if self.stop_event.is_set():
                    break
                try:
                    segment = segment_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                if segment is None:
                    break
                if skip_samples >= len(segment):
                    skip_samples -= len(segment)
                    continue
                if skip_samples > 0:
                    segment = segment[skip_samples:]
                    skip_samples = 0

                if self._play_segment(segment, stream):
                    break
        finally:
            stream.stop()
            stream.close()
            with self.play_lock:
                if self.is_playing and not self.is_paused:
                    self.offset_ms = 0
                    self.offset_samples = 0
                self.is_playing = False
            self._notify_state()

    def _play_segment(self, segment, stream):
        position = 0
        total = len(segment)
        self.current_segment_start_samples = self.offset_samples
        self.current_segment_len_samples = total
        self.start_time = time.time()

        while position < total:
            if self.stop_event.is_set():
                return True
            if not self.resume_event.is_set():
                if stream.active:
                    stream.stop()
                while not self.resume_event.wait(timeout=0.1):
                    if self.stop_event.is_set():
                        return True
                stream.start()

            end = min(position + BLOCK_SIZE, total)
            block = segment[position:end]
            stream.write(block.reshape(-1, 1))
            written = end - position
            position = end
            self.offset_samples += written
            self.offset_ms = self._samples_to_ms(self.offset_samples)
        return False

    def pause(self):
        with self.play_lock:
            if not self.is_playing or self.is_paused:
                return
            self.is_paused = True
            self.resume_event.clear()
        self._notify_state()

    def resume(self):
        with self.play_lock:
            if not self.is_paused:
                return
            self.is_paused = False
            self.resume_event.set()
        self._notify_state()

    def stop(self):
        with self.play_lock:
            self.is_playing = False
            self.is_paused = False
            self.offset_ms = 0
            self.offset_samples = 0
            self.text = ""
            self.stop_event.set()
            self.resume_event.set()
        self._notify_state()

    def get_offset_ms(self):
        with self.play_lock:
            return self.offset_ms
