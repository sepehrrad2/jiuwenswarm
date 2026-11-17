---
name: health-record-review
description: Log, find, and review migraine diary entries, and resume optional questions for a saved attack.
---

# Migraine diary

- Use `save_migraine_entry` to log a new attack. Save only what the user
  reported. Ask the returned `next_question` and end the turn. Wait for
  the user's answer before updating the same record ID. If the tool
  asks for the attack date and the user already supplied it, ask them
  to confirm it. Keep the attack date separate from the log date.
- Basic logging is the default. After a basic save with no next
  question, summarize the entry and tell the user they can type
  “Continue the optional questions for this entry.” End without a question.
- Pass `ask_optional=True` to start or resume optional questions.
  Omit it for ordinary answers. Pass `ask_optional=False` only when
  the user explicitly asks to pause. Save a skip only when the user
  explicitly asks to skip that field.
- Record medications as reported for that attack. Save regular
  medications only after the user confirms they apply to that attack.
  Use an empty list for regular medications only when the user reports none.
- Use `find_migraine_entries` for date-based lookup. Use `attack_date`
  for when the headache started and `log_date` for when it was logged.
  Resolve relative dates against the user's local calendar date. Ask
  for clarification if the date or its meaning is unclear.
- If several entries match, show the choices and wait before opening
  or updating any entry. If none match, ask for another date or ID.
  An update request does not authorize creating a new entry.
- Use `get_health_record` to reopen an entry by ID. For a dates-only
  request, show the stored attack and log dates in chat.
