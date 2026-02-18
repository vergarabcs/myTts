import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class TtsQueueController:
	def __init__(self, player, poll_interval=0.1):
		self.player = player
		self._queue = deque()
		self._lock = threading.Lock()
		self._stop_event = threading.Event()
		self._poll_interval = poll_interval
		self._worker = threading.Thread(target=self._queue_worker, daemon=True)
		self._worker.start()

	def _queue_worker(self):
		while not self._stop_event.is_set():
			with self._lock:
				if (
					self._queue
					and not self.player.is_playing
					and not self.player.is_paused
				):
					text = self._queue.popleft()
					self.player.load_text(text)
					self.player.play()
			time.sleep(self._poll_interval)

	def speak(self, text):
		clean_text = (text or "").strip()
		if not clean_text:
			return False

		with self._lock:
			self._queue.clear()
			self.player.load_text(clean_text)
			self.player.play()
		return True

	def add_to_queue(self, text):
		clean_text = (text or "").strip()
		if not clean_text:
			return False

		with self._lock:
			self._queue.append(clean_text)
		return True

	def stop(self):
		with self._lock:
			self._queue.clear()
			self.player.stop()

	def queue_size(self):
		with self._lock:
			return len(self._queue)

	def shutdown(self):
		self._stop_event.set()
		self._worker.join(timeout=1.0)


class _TtsRequestHandler(BaseHTTPRequestHandler):
	controller = None

	def do_OPTIONS(self):
		self.send_response(204)
		self._send_common_headers()
		self.end_headers()

	def do_POST(self):
		if self.path not in ("/speak", "/addToQueue", "/stop"):
			self._send_json(404, {"error": "Not found"})
			return

		if self.path == "/stop":
			self.controller.stop()
			self._send_json(200, {"ok": True, "queue_size": self.controller.queue_size()})
			return

		payload = self._read_json_body()
		if payload is None:
			self._send_json(400, {"error": "Invalid JSON body"})
			return

		text = payload.get("text") if isinstance(payload, dict) else None
		if not isinstance(text, str) or not text.strip():
			self._send_json(400, {"error": "Field 'text' must be a non-empty string"})
			return

		if self.path == "/speak":
			self.controller.speak(text)
			self._send_json(200, {"ok": True, "queue_size": self.controller.queue_size()})
			return

		self.controller.add_to_queue(text)
		self._send_json(200, {"ok": True, "queue_size": self.controller.queue_size()})

	def _read_json_body(self):
		try:
			content_length = int(self.headers.get("Content-Length", "0"))
		except ValueError:
			return None

		if content_length <= 0:
			return {}

		raw = self.rfile.read(content_length)
		try:
			return json.loads(raw.decode("utf-8"))
		except (json.JSONDecodeError, UnicodeDecodeError):
			return None

	def _send_common_headers(self):
		self.send_header("Content-Type", "application/json")
		self.send_header("Access-Control-Allow-Origin", "*")
		self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
		self.send_header("Access-Control-Allow-Headers", "Content-Type")

	def _send_json(self, status_code, payload):
		body = json.dumps(payload).encode("utf-8")
		self.send_response(status_code)
		self._send_common_headers()
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		self.wfile.write(body)

	def log_message(self, _format, *_args):
		return


class LocalTtsHttpServer:
	def __init__(self, controller, host="127.0.0.1", port=8765):
		self.controller = controller
		self.host = host
		self.port = port
		handler_class = type("TtsRequestHandler", (_TtsRequestHandler,), {})
		handler_class.controller = controller
		self._server = ThreadingHTTPServer((host, port), handler_class)
		self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

	def start(self):
		self._thread.start()

	def shutdown(self):
		self._server.shutdown()
		self._server.server_close()
		self._thread.join(timeout=1.0)


def start_local_tts_server(player, host="127.0.0.1", port=8765):
	controller = TtsQueueController(player)
	server = LocalTtsHttpServer(controller=controller, host=host, port=port)
	server.start()
	return server, controller