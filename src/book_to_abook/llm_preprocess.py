"""LLM preprocessing helpers for the book->audiobook pipeline.

Provide a helper that scans text for code snippets and replaces them
with high-level descriptions obtained from an LLM (e.g. Ollama).

The actual call to Ollama is pluggable via `ollama_fn(prompt)` so this
module doesn't assume a single transport. A convenience HTTP-based
helper is included that attempts common local Ollama endpoints.
"""

from typing import Callable, Dict, Optional
import re
import json
import subprocess

try:
	import requests
except Exception:  # pragma: no cover - requests may be absent in test env
	requests = None


# default_ollama_http_generate is implemented below using the confirmed
# streaming `/api/generate` endpoint and CLI-assisted model detection.
    
def default_ollama_http_generate(prompt: str, model: str = "ollama:default") -> str:
	"""Call the local Ollama HTTP `/api/generate` endpoint and return text.

	This function assumes a local Ollama server at `http://127.0.0.1:11434`.
	The endpoint streams newline-delimited JSON (NDJSON). We consume the
	stream and concatenate `response` fragments until an item with
	`done: true` is received.

	If `model` is the placeholder `ollama:default`, we attempt to detect
	a suitable model via the `ollama list` CLI and pick the first non-embedding
	model.
	"""
	if requests is None:
		raise RuntimeError("requests is not installed; provide a custom ollama_fn")

	if model == "ollama:default" or not model:
		# try to detect an installed model via the `ollama` CLI
		try:
			proc = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True)
			lines = [l for l in proc.stdout.splitlines() if l.strip()]
			# skip header if present
			candidates = []
			for ln in lines:
				parts = ln.split()
				if not parts:
					continue
				name = parts[0]
				# skip embeddings and obvious non-text models
				lname = name.lower()
				if "embed" in lname or "embedding" in lname:
					continue
				candidates.append(name)
			if not candidates:
				raise RuntimeError("No non-embedding models found via `ollama list`")
			model = candidates[0]
		except Exception as exc:
			raise RuntimeError(f"Could not detect Ollama model via CLI: {exc}")

	url = "http://127.0.0.1:11434/api/generate"
	payload = {"model": model, "prompt": prompt}

	try:
		resp = requests.post(url, json=payload, stream=True, timeout=60)
	except Exception as exc:
		raise RuntimeError(f"HTTP request to Ollama failed: {exc}")

	if resp.status_code != 200:
		# try to parse JSON error body
		try:
			j = resp.json()
			err = j.get("error") or j.get("message") or str(j)
		except Exception:
			err = resp.text.strip()
		raise RuntimeError(f"Ollama API error ({resp.status_code}): {err}")

	# stream is NDJSON with objects containing a `response` fragment
	pieces = []
	try:
		for raw in resp.iter_lines(decode_unicode=True):
			if not raw:
				continue
			try:
				item = json.loads(raw)
			except Exception:
				# ignore non-json lines
				continue
			# collect 'response' fields
			if isinstance(item, dict) and "response" in item:
				fragment = item.get("response") or ""
				pieces.append(fragment)
			if isinstance(item, dict) and item.get("done"):
				break
	finally:
		try:
			resp.close()
		except Exception:
			pass

	return "".join(pieces).strip()


def describe_and_replace_codes(
	text: str,
	ollama_fn: Optional[Callable[[str], str]] = None,
	model: str = "ollama:default",
	chunk_size: int = 4000,
) -> str:
	"""Detect code snippets and replace each with a single LLM-generated description.

	- Detects fenced code blocks (```...```) and inline code (`...`).
	- Calls the LLM once per detected code snippet (no chunking).
	- `ollama_fn` if omitted will use a best-effort local HTTP helper.

	Returns the modified text.
	"""
	if ollama_fn is None:
		def _ollama(p: str) -> str:
			return default_ollama_http_generate(p, model=model)

		ollama_fn = _ollama

	# regexes
	fenced_re = re.compile(r"```(?:[^\n]*\n)?(.*?)```", re.DOTALL)
	inline_re = re.compile(r"`([^`]+)`")

	cache: Dict[str, str] = {}

	def describe(code: str) -> str:
		if code in cache:
			return cache[code]
		prompt = (
			"Provide a short, high-level, human-readable description (1-3 sentences) "
			"of the following code snippet. Be explicit about purpose and behavior:\n\n" + code
		)
		try:
			desc = ollama_fn(prompt)
		except Exception as exc:
			desc = f"[Description unavailable: {exc}]"
		cache[code] = desc
		return desc

	# Replace fenced blocks across the whole text; one LLM call per block
	def _fenced_sub(m: re.Match) -> str:
		code = m.group(1).strip()
		d = describe(code)
		return f"[Code description]\n{d}\n"

	processed = fenced_re.sub(_fenced_sub, text)

	# Then replace inline code; one LLM call per inline snippet
	def _inline_sub(m: re.Match) -> str:
		code = m.group(1).strip()
		d = describe(code)
		one_line = " ".join(d.splitlines())
		return f"[code: {one_line}]"

	processed = inline_re.sub(_inline_sub, processed)

	return processed


__all__ = ["describe_and_replace_codes", "default_ollama_http_generate"]
