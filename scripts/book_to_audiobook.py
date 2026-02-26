import argparse
import sys
from pathlib import Path

import numpy as np
from datetime import datetime

# Ensure project root is on sys.path so `src` package imports work when
# running the script directly (not via pytest which sets PYTHONPATH).
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from kokoro import KPipeline
from src.constants import SAMPLE_RATE, VOICE, SPEED, VOLUME
from src.book_to_abook.llm_preprocess import describe_and_replace_codes


def text_to_mp3(in_path: Path, out_path: Path, lang_code: str = "a", voice: str = VOICE, speed: float = SPEED):
	text = in_path.read_text(encoding="utf-8")

	print("Running LLM preprocess to replace/describe code snippets...")
	processed = describe_and_replace_codes(text)

	# Append the LLM-processed text to a log for later inspection
	log_path = PROJECT_ROOT / "book_to_abook.log"
	try:
		with log_path.open("a", encoding="utf-8") as fh:
			fh.write(f"\n--- {datetime.utcnow().isoformat()}Z ---\n")
			fh.write(processed)
			fh.write("\n")
	except Exception as exc:
		print(f"Warning: failed to write log {log_path}: {exc}")

	print("Initializing TTS pipeline...")
	pipeline = KPipeline(lang_code=lang_code)

	print("Synthesizing audio segments...")
	segs = []
	for _t, _meta, audio in pipeline(processed, voice=voice, speed=speed, split_pattern=r"\n+"):
		if audio is None:
			continue
		arr = np.asarray(audio, dtype=np.float32)
		arr = arr * VOLUME
		arr = np.clip(arr, -1.0, 1.0)
		int16 = (arr * 32767.0).astype(np.int16)
		segs.append(int16)

	if not segs:
		raise RuntimeError("No audio segments produced by the TTS pipeline.")

	combined = np.concatenate(segs)

	try:
		from pydub import AudioSegment

		raw = combined.tobytes()
		audio_seg = AudioSegment(
			data=raw,
			sample_width=2,
			frame_rate=SAMPLE_RATE,
			channels=1,
		)
		print(f"Exporting MP3 to: {out_path}")
		audio_seg.export(str(out_path), format="mp3", bitrate="192k")
	except Exception as exc:
		# Fallback: write WAV if pydub/ffmpeg unavailable
		wav_path = out_path.with_suffix(".wav")
		try:
			import soundfile as sf

			print(f"pydub/ffmpeg not available, writing WAV to: {wav_path}")
			sf.write(str(wav_path), combined.astype(np.float32), SAMPLE_RATE, subtype="PCM_16")
			print(f"WAV written: {wav_path}. Convert to MP3 with ffmpeg if desired.")
		except Exception:
			raise RuntimeError(f"Failed to export audio: {exc}")


def parse_args():
	p = argparse.ArgumentParser(description="Convert a .txt file to a single MP3 using kokoro TTS.")
	p.add_argument("infile", type=Path, help="Input .txt file")
	p.add_argument("outfile", type=Path, nargs="?", help="Output .mp3 file (optional)")
	p.add_argument("--lang", default="a", help="Language code for KPipeline")
	p.add_argument("--voice", default=VOICE, help="Voice id")
	p.add_argument("--speed", type=float, default=SPEED, help="Playback speed multiplier")
	return p.parse_args()


def main():
	args = parse_args()
	infile = args.infile
	outfile = args.outfile or infile.with_suffix(".mp3")
	text_to_mp3(infile, outfile, lang_code=args.lang, voice=args.voice, speed=args.speed)


if __name__ == "__main__":
	main()
