---
name: exam-from-chapter
description: Generate multiple high-quality Exam Questions in strict JSON format from a provided book chapter or section.
argument-hint: "Paste chapter text"
user-invokable: true
disable-model-invocation: true
---

## Goal

Transform chapter text into clear, accurate, exam-like multiple choice questions.

## Input Expectations

- User provides full chapter text, a chapter excerpt, or a chapter summary.
- number of questions to generate

## Output Contract (strict)

Create valid JSON file. Do not include markdown fences, comments, or extra prose.

Use this exact top-level shape (array of card objects):

[
  {
    "question": "<question>",
    "answer": "<answer>",
    "choices": ["<choice1>", "<choice2>", "<choice3>", "<choice4>"],
    "rationale": "<why answer is correct and why alternatives are less suitable>",
    "citation": "<source text that supports the answer>"
  }
]

## Card Rules

* Cover distinct concepts; avoid duplicates.
* Keep each `question` to one clear multiple-choice prompt.
* Keep each `answer` concise and exactly matching one value in `choices`.
* Provide exactly 4 choices per card.
* Ensure distractors are plausible and from the same topic domain.
* Keep `rationale` concise but sufficient to justify the correct answer. Explain why alternatives are less suitable.
* Create questions that require reasoning and understanding, not just recall.
* Do not assume the exam taker has access to the chapter text during the exam. If you need to reference something, include the necessary context within the question itself.
* IMPORTANT: the citation must be a direct copy from the chapter text, not a paraphrase or summary. It's not valid if I can't use it to search the chapter and find the supporting text. Keep it short, it doesn't have to be a full sentence.
* Make 20% of the questions more challenging by including needing to combine multiple facts and requiring multi-step reasoning.

## Bad Example and how to correct it

1. The question and rationale references the chapter text instead of being self-contained.
2. The choices are implausible: only one is positive, the rest are obviously negative, making the answer trivial.
3. rationale should explain why the other choices are incorrect

```json
{
  "question": "According to the chapter, which dietary pattern does the chapter associate with reduced mortality and slower progression of CKD?",
  "answer": "Predominantly plant-based diet",
  "choices": [
    "Predominantly plant-based diet",
    "High red-meat, low-fiber diet",
    "Highly processed, high-sodium diet",
    "High-fructose beverage–based diet"
  ],
  "rationale": "The chapter reports that predominantly plant-based diets are associated with reduced overall mortality in CKD and can slow progression; the other options are linked in the text to increased CKD risk or adverse metabolic effects.",
  "citation": "Predominantly plant-based diets are associated with reduced overall mortality risk in CKD"
}
```

How to correct it:
1. Make the question self-contained (do not reference the chapter or require outside context).
2. Use plausible distractors—choices that are reasonable and require actual knowledge or reasoning to eliminate.
3. In the rationale, explain not only why the correct answer is right but also why the other options are less suitable based on the chapter content.

Corrected example — self-contained and with plausible distractors:

```json
{
  "question": "Which dietary pattern is associated with reduced mortality and slower progression of chronic kidney disease (CKD)?",
  "answer": "Predominantly plant-based diet",
  "choices": [
    "Mediterranean-style diet",
    "Low-protein (0.6 g/kg) diet",
    "Predominantly plant-based diet",
    "DASH diet"
  ],
  "rationale": "Predominantly plant-based diets are associated with reduced mortality and slower CKD progression because they increase dietary fiber, lower net endogenous acid load, and reduce exposure to animal-protein–derived nephrotoxins. Mediterranean-style and DASH diets are healthful and benefit cardiovascular risk and blood pressure, respectively, but are not emphasized here for both reduced CKD mortality and slower eGFR decline. Low-protein (0.6 g/kg) diets may help reduce nitrogenous waste and slow progression in some studies, but they do not capture the broader mortality and microbiome-related benefits attributed to plant-based diets, making the plant-based choice the best-supported option.",
}
```

## Good Examples
See good examples from Board Review Questions.