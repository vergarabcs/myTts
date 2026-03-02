#!/bin/bash

# Runner script for ollama_anki_from_epub_out.py
# Activates virtual environment if present and runs the Python script

set -e  # Exit on any error

 # Determine venv python if available
VENV_PY=""
if [ -x ".venv/Scripts/python.exe" ]; then
    VENV_PY=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ]; then
    VENV_PY=".venv/bin/python"
fi

if [ -n "$VENV_PY" ]; then
    PY_CMD="$VENV_PY"
else
    PY_CMD="python"
fi

# Ensure project root is on PYTHONPATH for Python imports
# Prefer Windows-style path when available (Git for Windows / MINGW)
PROJECT_PYTHONPATH=""
if command -v pwd >/dev/null 2>&1 && pwd -W >/dev/null 2>&1; then
    PROJECT_PYTHONPATH="$(pwd -W)"
else
    PROJECT_PYTHONPATH="$(pwd)"
fi
export PYTHONPATH="${PROJECT_PYTHONPATH}${PYTHONPATH:+:}$PYTHONPATH"

echo "Running ollama_anki_from_epub_out.py with hardcoded arguments using $PY_CMD..."
"$PY_CMD" ollama_anki_from_epub_out.py \
    --input-dir sample/sample_chunks \
    --output-file sample/infrastructure_as_code.txt \
    --provider openai \
    --deck Audio::Everything \
    --chunk-size 5000 \
    --overlap 400 \
    --model gpt-5-mini \
    # --chunk-range 3-12
    # --model gpt-oss:120b-cloud \

# "$PY_CMD" scripts/generate_embeddings.py \
#     --input-tsv "/c/Users/Bill/Documents/Audio__Everything.txt" \
#     --model embeddinggemma:300m \
#     --out-embeddings sample/anki_embeddings.json \
#     --batch-size 64

# "$PY_CMD" scripts/visualize_memory_map.py \
#     --input-tsv "/c/Users/Bill/Documents/Audio__Everything.txt" \
#     --in-embeddings sample/anki_embeddings.json \
#     --out-neighbors sample/anki_neighbors.json \
#     --out-plot sample/anki_map.png \
#     --k 6 \
#     --layout pca \
#     --seed 42

echo "Script completed successfully."