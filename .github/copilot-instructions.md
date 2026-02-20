# Project Guidelines

These instructions assume Windows paths and the workspace .venv for Python commands.

## Code Style
- Use PascalCase for classes and snake_case for methods/functions. Examples: [src/epub_reader.py](src/epub_reader.py#L19), [src/player.py](src/player.py#L11-L176).
- Keep module-level constants uppercase in the shared constants module. Example: [src/constants.py](src/constants.py#L1-L5).
- Tests follow pytest naming (test_*) and use simple helpers/fakes. Prefer colocating new tests with code (for memory map: [src/memory_map/tests/](src/memory_map/tests/)).