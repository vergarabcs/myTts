import json
import re
from typing import List

from pydantic import (
	BaseModel,
	ConfigDict,
	RootModel,
	ValidationError,
	field_validator,
	model_validator,
)

from src.anki_gen.json_processor import extract_json_text


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


class AnkiCard(BaseModel):
	model_config = ConfigDict(extra="forbid")

	question: str
	answer: str
	options: list[str]
	explanation: str
	topic: str
	tags: list[str] = []

	@field_validator("question", "answer", "explanation", "topic")
	@classmethod
	def validate_text_fields(cls, value: str) -> str:
		cleaned = value.strip()
		if not cleaned:
			raise ValueError("Field cannot be empty")
		return cleaned

	@field_validator("options")
	@classmethod
	def validate_options(cls, value: list[str]) -> list[str]:
		options = [option.strip() for option in value if option.strip()]
		if len(options) != 3:
			raise ValueError("options must contain exactly 3 non-empty choices")
		return options

	@field_validator("tags")
	@classmethod
	def validate_tags(cls, value: list[str]) -> list[str]:
		return [tag.strip() for tag in value if tag.strip()]

	@model_validator(mode="after")
	def validate_answer_is_option(self) -> "AnkiCard":
		if self.answer in self.options:
			return self

		normalized_answer = self.answer.strip().lower()
		for option in self.options:
			if option.strip().lower() == normalized_answer:
				self.answer = option
				return self

		raise ValueError("answer must be present in options")


class CardsPayload(BaseModel):
	model_config = ConfigDict(extra="forbid")

	cards: list[AnkiCard]


class CardsList(RootModel[list[AnkiCard]]):
	pass


def parse_cards_content(content: object) -> list[dict]:
	if isinstance(content, dict):
		payload = CardsPayload.model_validate(content)
		return [card.model_dump() for card in payload.cards]

	if isinstance(content, list):
		payload = CardsList.model_validate(content)
		return [card.model_dump() for card in payload.root]

	if not isinstance(content, str):
		raise ValueError("Ollama response content must be a string, list, or dict")

	raw_text = content.strip()
	if raw_text.startswith("{") or raw_text.startswith("["):
		try:
			parsed = json.loads(raw_text)
		except json.JSONDecodeError:
			parsed = None
		if isinstance(parsed, dict):
			payload = CardsPayload.model_validate(parsed)
			return [card.model_dump() for card in payload.cards]
		if isinstance(parsed, list):
			payload = CardsList.model_validate(parsed)
			return [card.model_dump() for card in payload.root]

	json_text = extract_json_text(content)
	try:
		payload = CardsPayload.model_validate_json(json_text)
		return [card.model_dump() for card in payload.cards]
	except ValidationError:
		payload = CardsList.model_validate_json(json_text)
		return [card.model_dump() for card in payload.root]