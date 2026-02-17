import argparse
import re
from pathlib import Path

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub


def clean_chapter_text(html_bytes: bytes) -> str:
    soup = BeautifulSoup(html_bytes, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    filtered = [line for line in lines if line]
    cleaned = "\n".join(filtered)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def chapter_title(html_bytes: bytes, fallback: str) -> str:
    soup = BeautifulSoup(html_bytes, "html.parser")

    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        if title:
            return title

    header = soup.find(["h1", "h2", "h3"])
    if header:
        value = header.get_text(strip=True)
        if value:
            return value

    return fallback or "Untitled"


def safe_filename(value: str, max_len: int = 80) -> str:
    value = re.sub(r"[\\/:*?\"<>|]", "_", value)
    value = re.sub(r"\s+", "_", value).strip("._ ")
    if not value:
        value = "Untitled"
    return value[:max_len]


def extract_epub_to_txt(epub_path: Path, out_dir: Path) -> int:
    if not epub_path.exists():
        raise FileNotFoundError(f"EPUB not found: {epub_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    for old_txt in out_dir.glob("*.txt"):
        old_txt.unlink()

    book = epub.read_epub(str(epub_path))
    items_by_id = {item.id: item for item in book.get_items()}

    written = 0
    for index, (spine_id, _linear) in enumerate(book.spine, start=1):
        item = items_by_id.get(spine_id)
        if not item or item.get_type() != ITEM_DOCUMENT:
            continue

        html_bytes = item.get_content()
        text = clean_chapter_text(html_bytes)
        if not text:
            continue

        fallback_title = Path(item.get_name() or "Untitled").stem
        title = chapter_title(html_bytes, fallback_title)
        filename = f"{written + 1:03d}_{safe_filename(title)}.txt"

        output_path = out_dir / filename
        output_path.write_text(text + "\n", encoding="utf-8")
        written += 1

    if written == 0:
        raise ValueError("No readable chapters found in the EPUB.")

    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract an EPUB into clean chapter text files."
    )
    parser.add_argument("epub_path", type=Path, help="Path to the .epub file")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("sample") / "epub_out",
        help="Output directory for chapter txt files (default: sample/epub_out)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    count = extract_epub_to_txt(args.epub_path, args.out_dir)
    print(f"Wrote {count} chapter file(s) to: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
