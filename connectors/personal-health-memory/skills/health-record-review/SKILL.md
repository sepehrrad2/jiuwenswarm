---
name: health-record-review
description: Answer questions about saved Personal Health Memory text records, including visits, tests, follow-up instructions, medication changes, and reported symptoms.
---

# Health record review

Use Personal Health Memory tools to answer questions about saved records.

- For a specific date or a complete list, use get_health_timeline with date, source, or record-type filters. For the latest two visits, select the two most recent visit notes in the timeline.
- For questions phrased differently from the notes, use search_health_records. For medication names, search both the supplied name and its verified alias when available. If search results may omit relevant dated notes, check the timeline too.
- Use get_health_record to open a note by ID when comparing records or quoting instructions. Cite the record ID and date for each finding.
- For the latest documented dose, look for an explicit dose instruction and check later records for changes, holds, or discontinuation. A later mention without a dose does not supersede a documented dose. If records conflict and do not resolve the conflict, cite both.
- Distinguish a temporary hold from a stop. When a dose, follow-up date, or other detail is absent, say it was not documented. Describe what the records say without issuing new treatment instructions.

## Migraine diary check-in

Use this workflow when the user asks to log a headache or migraine episode.
Treat the entry as the patient's report.

1. Draft the entry from what the patient already shared. Capture the attack
   date, approximate start time, severity (0–10 if given), end time or ongoing
   status, medication name and time as reported, any relief and its timing,
   and impact on daily activities.
2. If the attack date is missing or ambiguous, ask for it first. After that,
   ask about one missing or ambiguous field per turn. Accept "skip" or
   "I don't remember" and leave that detail unknown. Keep approximate times
   approximate. If the patient gives a relative date, show the resolved date
   in the preview when it can be determined.
3. Show the draft with the patient's original account and any corrections.
   Ask the patient to confirm before calling save_health_record. If the
   patient changes a detail, show the updated draft for confirmation.
4. On confirmation, call save_health_record with a unique record ID,
   source "Migraine diary", and the attack date as the record date. If the
   attack date is unknown, use the log date as the record date and explicitly
   label it "Log date" in the entry. Return the ID so the patient can reopen
   it using get_health_record.

Describe symptoms, medication use, and relief as reported. Preserve the
sequence of events without assigning a cause, diagnosing the episode, or
recommending medication changes.

## Guided migraine diary and medication profile

Use these instructions for migraine diary and medication-profile requests.
For migraine logging, this workflow takes precedence over older diary
instructions in this skill.

- When the user asks to log a new attack, call `save_migraine_entry` without
  a record ID. Save only what the user reported. Keep its returned ID for
  follow-ups. Ask the user for the attack date, or confirm it if they already
  supplied one. Wait for their response before updating that ID.
- For follow-ups, pass the same record ID and only the new or corrected
  fields. When the tool returns `next_question`, ask that question and
  wait for the answer before making another update.
- Use basic logging by default. For an existing entry, pass its record ID
  and `ask_optional=True` when the user asks to start or resume optional
  questions. Omit `ask_optional` when saving an ordinary answer so the
  tool keeps the entry's saved setting. Pass `ask_optional=False` only
  when the user explicitly asks to pause or stop optional questions.
- If the user explicitly skips an optional question, pass its returned
  `next_field` as `skip_field`. Leave unreported details unknown. Use
  `None reported` for a text field only when the user explicitly says
  there was none. Let the user stop and resume later.
- Use `get_medication_profile` to read the current self-reported list.
  Show the proposed full replacement list and wait for confirmation
  before calling `save_medication_profile`. Use an empty list only when
  the user explicitly reports taking no regular or preventive medication.
- The current profile can help prompt recall. Save it as an attack's
  `regular_medications` only after the user confirms it applied at the
  time of that attack. Use `get_health_record` to reopen a saved entry.

## How to start optional diary questions

Use basic logging by default. After completing a basic entry, tell the
user the optional questionnaire is off by default and show this phrase:
“Continue the optional questions for this entry.” Give it as a tip and
end the reply without asking another question.

When the user explicitly asks to start or resume optional questions,
pass `ask_optional=True` with the existing record ID. Omit `ask_optional`
on ordinary answers. Pass `ask_optional=False` for an explicit pause.
Ask only the tool’s returned question, then wait for the user. When the
tool says the questionnaire is finished, say so and end the reply.

## Find a saved migraine entry before updating it

- Reuse the record ID when the user explicitly provides it or clearly
  refers to the one entry already being discussed.
- For an entry described by date, call `find_migraine_entries` before
  saving any changes. Use `attack_date` for “started two days ago” and
  `log_date` for “I logged it yesterday.”
- Resolve relative dates against the user's local calendar date. If the
  date cannot be resolved reliably, ask for the calendar date. If the
  wording could refer to either date, ask whether they mean when the
  headache started or when it was logged.
- When exactly one entry matches, use its record ID for the requested
  update or questionnaire resume.
- When multiple entries match, show their start times and severity, with
  record IDs if needed to tell them apart. Ask which entry the user means
  and wait for their choice before calling `save_migraine_entry`.
- When no entries match, report that and ask for a different date or an
  existing record ID. An update request does not authorize a new entry.
