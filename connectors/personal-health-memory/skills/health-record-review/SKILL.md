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
