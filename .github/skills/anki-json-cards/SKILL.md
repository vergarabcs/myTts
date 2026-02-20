---
name: anki-json-cards
description: Generate multiple high-quality Anki flashcards in strict JSON format from a provided book chapter or section.
argument-hint: "Paste chapter text or describe chapter focus, optional: target card count and difficulty"
user-invokable: true
disable-model-invocation: true
---

# Anki JSON Cards

Use this skill when the user provides chapter content and wants multiple Anki cards in JSON file.

## Goal

Transform chapter text into clear, accurate, study-ready flashcards.

## Input Expectations

- User provides full chapter text, a chapter excerpt, or a chapter summary.

## Output Contract (strict)

Create valid JSON file. Do not include markdown fences, comments, or extra prose.

Use this exact top-level shape (array of card objects):

[
  {
    "question": "<question>",
    "answer": "<answer>",
    "choices": ["<choice1>", "<choice2>", "<choice3>"],
    "explanation": "<why answer is correct and why alternatives are less suitable>",
    "topic": "<main topic or concept this card tests>",
    "tags": "flagged,s3"
  }
]

## Card Rules

* Generate as many card as you can without being repetitive.
* Cover distinct concepts; avoid duplicates.
* Keep each `question` to one clear multiple-choice prompt.
* Keep each `answer` concise and exactly matching one value in `choices`.
* Provide exactly 3 choices per card.
* Ensure distractors are plausible and from the same topic domain.
* Keep `explanation` concise but sufficient to justify the correct answer. Explain why alternatives are less suitable.
* Prefer fact-based cards directly supported by the provided chapter.
* Prefer scenario-based or applied questions over pure recall when possible.
* If you notice content that conflicts with your training data, tag it with 'flagged'.

## Safety / Quality Checks

Before final output, verify:

- JSON parses successfully.
- Output is a JSON array of card objects.
- No empty fields.
- No duplicate `question` values.
- Every `answer` appears in `choices`.
- Answers and explanations are grounded in provided source text.

## Example Invocation

- `/anki-json-cards Chapter 3: AWS Data Storage ...`
