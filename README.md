# myTts

This repository contains small personal tools for text-to-speech (TTS) workflows and generating Anki flashcards from EPUB/text output. Two primary utilities are:

- [tts_hotkey.py](tts_hotkey.py): system-wide hotkey to copy selected text and speak it via a local TTS server.
- [ollama_anki_from_epub_out.py](ollama_anki_from_epub_out.py): split chapter text into chunks and generate Anki TSV rows using an LLM provider.

**Quick Highlights**
- **TTS hotkey**: press Alt+` to copy the current selection and speak it using the local TTS server.
- **Anki generator**: processes chapter .txt files (sample/epub_out) into an Anki-importable TSV and logs failures.

**When to use**: fast personal workflows for reading selections aloud and for converting book/text content into study cards.

## Requirements

- Python 3.10+ (recommended)
- Windows for `tts_hotkey.py` (it uses `pywin32` and `keyboard`)
- See [requirements.txt](requirements.txt) for pinned dependencies

## Setup

1. Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2. Optional: configure any environment variables your LLM provider requires (e.g., `OPEN_AI_KEY` for OpenAI provider used by the Anki generator).

## Usage

**TTS Hotkey**

- Script: [tts_hotkey.py](tts_hotkey.py)
- Description: registers global hotkey `Alt+`` that saves the current clipboard state, issues `Ctrl+C` to copy the current selection, restores the clipboard, and sends the copied text to a local TTS controller. It starts a local HTTP TTS server at `http://127.0.0.1:8765`.

Run:

```bash
python tts_hotkey.py
```

API endpoints exposed while running:

- `POST /speak` — JSON: `{ "text": "..." }`
- `POST /addToQueue` — JSON: `{ "text": "..." }`
- `POST /stop` — stop playback

Notes:
- The hotkey implementation depends on Windows clipboard APIs and the `keyboard` library. Run with appropriate privileges if global hotkeys don't register.
- The `kokoro` pipeline and `src/tts` modules handle the speech backend. See `src/tts` for implementation details.

**Generate Anki TSV from EPUB text files**

- Script: [ollama_anki_from_epub_out.py](ollama_anki_from_epub_out.py)
- Description: reads chapter `.txt` files in `sample/epub_out`, splits them into overlapping chunks, calls an LLM (Ollama or OpenAI) to produce candidate cards, deduplicates, and writes a TSV compatible with Anki import.

Run (example):

```bash
python ollama_anki_from_epub_out.py --input-dir sample/epub_out --output-file sample/anki_out.txt --provider openai --model "gpt-4"
```

Key flags:
- `--input-dir`: directory of chapter `.txt` files (default: `sample/epub_out`)
- `--output-file`: TSV output (default: `sample/anki_out.txt`)
- `--provider`: `ollama` or `openai`
- `--chunk-size` / `--overlap`: control chunking behavior
- `--limit-chunks` / `--chunk-range`: limit or select global chunk range for partial runs

Outputs:
- A TSV with Anki header lines (tab-separated) and card rows.
- A `.failed.jsonl` file is created alongside the output when chunks or LLM calls fail.

## Development notes

- Follow repository style: PascalCase for classes, snake_case for functions.
- Tests live in `tests/` and use `pytest`.
- Small scripts for embedding generation, visualization, and server utilities are under `scripts/` and `src/`.

## Troubleshooting

- If hotkey does not copy text reliably, increase the clipboard wait timeout in `tts_hotkey.py` (`_wait_for_clipboard_text`).
- For Anki generation, inspect the `.failed.jsonl` log for failed chunks and model responses.

## License & Notes

This workspace is for personal tooling and experimentation. No license file is included by default.

If you want me to add example workflows, CI, or packaging instructions, tell me which you'd like next.
