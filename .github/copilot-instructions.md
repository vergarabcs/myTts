# Project Guidelines

These instructions assume Windows paths and the workspace .venv for Python commands.

## Code Style
- Use PascalCase for classes and snake_case for methods/functions. Examples: [src/epub_reader.py](src/epub_reader.py#L19), [src/player.py](src/player.py#L11-L176).
- Keep module-level constants uppercase in the shared constants module. Example: [src/constants.py](src/constants.py#L1-L5).
- Tests follow pytest naming (test_*) and use simple helpers/fakes. Example: [tests/test_player.py](tests/test_player.py#L7-L97).

## Architecture
- GUI entry point builds a Qt app and launches EpubReaderApp. See [epub_kokoro_reader.py](epub_kokoro_reader.py#L1-L19).
- EpubReaderApp orchestrates UI, EPUB parsing, and playback via TtsPlayer and ReaderState. See [src/epub_reader.py](src/epub_reader.py#L19-L211).
- TtsPlayer encapsulates audio streaming, playback state, and threading. See [src/player.py](src/player.py#L11-L189).
- ReaderState persists book path and position to a JSON file. See [src/state.py](src/state.py#L7-L32).
- A separate hotkey-driven TTS script lives outside the GUI flow. See [tts_hotkey.py](tts_hotkey.py#L1-L163).

## Build and Test
- Use the workspace .venv for all Python commands.
- Run tests: `.venv\Scripts\python.exe -m pytest`
- Run GUI app: `.venv\Scripts\python.exe epub_kokoro_reader.py`
- Run hotkey script: `.venv\Scripts\python.exe tts_hotkey.py`

## Project Conventions
- Playback and UI settings share constants like sample rate, voice, speed, and block size. See [src/constants.py](src/constants.py#L1-L5) and [src/player.py](src/player.py#L8-L103).
- Reader state persists to `.tts_reader_state.json` in the working directory. See [src/state.py](src/state.py#L13-L32).
- EPUB content is extracted to a temp directory with prefix `epub_reader_`. See [src/epub_reader.py](src/epub_reader.py#L218-L251).

## Integration Points
- Qt UI and WebEngine render EPUB HTML content. See [src/epub_reader.py](src/epub_reader.py#L11-L71).
- EPUB parsing uses `ebooklib`; text extraction uses BeautifulSoup. See [src/epub_reader.py](src/epub_reader.py#L8-L241).
- TTS uses `kokoro.KPipeline`. See [src/epub_reader.py](src/epub_reader.py#L10-L31) and [tts_hotkey.py](tts_hotkey.py#L10-L156).
- Audio output uses `sounddevice`. See [src/player.py](src/player.py#L5-L103) and [tts_hotkey.py](tts_hotkey.py#L5-L127).
- Hotkey script uses global keyboard hooks and clipboard access. See [tts_hotkey.py](tts_hotkey.py#L4-L163).

## Security
- Hotkey script reads/writes clipboard and sends synthetic key events. See [tts_hotkey.py](tts_hotkey.py#L26-L147).
- EPUB extraction writes to a temp directory and loads local files into the embedded web view. See [src/epub_reader.py](src/epub_reader.py#L155-L251).
- Reader state is stored locally in a JSON file. See [src/state.py](src/state.py#L25-L32).
