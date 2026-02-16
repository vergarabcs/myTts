import json
import re


def sanitize_tag(value: str) -> str:
	cleaned = re.sub(r"\s+", "_", value.strip())
	cleaned = re.sub(r"[^a-zA-Z0-9_:-]", "", cleaned)
	return cleaned


def build_tsv_row_from_card(card: dict, deck: str) -> str:
	note_type = str(card.get("note_type", "")).strip()
	if note_type and note_type != "MultipleChoice":
		raise ValueError("Only MultipleChoice is supported")

	row = [""] * 14
	row[0] = "MultipleChoice"
	row[1] = deck

	raw_tags = card.get("tags", [])
	tags: list[str] = []
	if isinstance(raw_tags, list):
		tags = [sanitize_tag(str(tag)) for tag in raw_tags if str(tag).strip()]

	question = str(card.get("question", "")).strip()
	answer = str(card.get("answer", "")).strip()
	options = card.get("options", [])
	explanation = str(card.get("explanation", "")).strip()
	topic = str(card.get("topic", "")).strip()

	if not question or not answer or not isinstance(options, list) or len(options) != 3:
		raise ValueError("Invalid MultipleChoice card fields")

	options_text = [str(option).strip() for option in options if str(option).strip()]
	if len(options_text) != 3 or answer not in options_text:
		raise ValueError("MultipleChoice options must be 3 and include answer")

	row[3] = question
	row[4] = answer
	row[5] = json.dumps(options_text, ensure_ascii=False)
	row[6] = explanation
	row[7] = topic

	row[13] = " ".join(tag for tag in tags if tag)
	return "\t".join(row)


def extract_rows_from_cards(cards: list[dict], deck: str) -> list[str]:
	rows: list[str] = []
	for card in cards:
		try:
			rows.append(build_tsv_row_from_card(card, deck=deck))
		except ValueError:
			continue
	return rows