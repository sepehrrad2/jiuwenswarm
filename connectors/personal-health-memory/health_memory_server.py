import json
import os
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import chromadb
from mcp.server.fastmcp import FastMCP


configured_data_dir = os.environ.get("HEALTH_MEMORY_DATA_DIR")
database_path = (
    Path(configured_data_dir).expanduser().resolve()
    if configured_data_dir
    else Path.home() / ".personal-health-memory" / "chroma_db"
)
client = chromadb.PersistentClient(path=str(database_path))
collection = client.get_or_create_collection("health_records")

mcp = FastMCP("personal-health-memory")
patient_filter = {"patient_id": "demo-patient"}


def format_records(ids, documents, metadatas):
    return [
        {
            "id": record_id,
            "date": metadata["date"],
            "source": metadata["source"],
            **({"record_type": metadata["record_type"]} if "record_type" in metadata else {}),
            "text": document,
        }
        for record_id, document, metadata in zip(ids, documents, metadatas)
    ]


@mcp.tool()
def search_health_records(question: str) -> list[dict[str, str]]:
    """Find relevant passages for a focused question about the demo patient."""
    results = collection.query(
        query_texts=[question],
        where=patient_filter,
        n_results=2,
        include=["documents", "metadatas"],
    )
    return format_records(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
    )


@mcp.tool()
def get_health_timeline(
    start_date: str | None = None,
    end_date: str | None = None,
    source: str | None = None,
    record_type: str | None = None,
) -> list[dict[str, str]]:
    """Return records in date order, filtered by inclusive dates, exact source, or type."""
    for value in (start_date, end_date):
        if value is not None and date.fromisoformat(value).isoformat() != value:
            raise ValueError("Dates must use YYYY-MM-DD.")
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError("Start date must be on or before end date.")

    results = collection.get(
        where=patient_filter,
        include=["documents", "metadatas"],
    )
    records = format_records(
        results["ids"], results["documents"], results["metadatas"]
    )
    matching = [
        record for record in records
        if (start_date is None or record["date"] >= start_date)
        and (end_date is None or record["date"] <= end_date)
        and (source is None or record["source"] == source)
        and (record_type is None or record.get("record_type") == record_type.strip().lower())
    ]
    return sorted(matching, key=lambda record: record["date"])


@mcp.tool()
def save_health_record(
    record_id: str,
    record_date: str,
    source: str,
    text: str,
    record_type: str | None = None,
) -> dict[str, str]:
    """Save a user-provided record with a stable ID and a YYYY-MM-DD date."""
    record_id = record_id.strip()
    record_date = record_date.strip()
    source = source.strip()
    text = text.strip()

    if not all((record_id, record_date, source, text)):
        raise ValueError("Record ID, date, source, and text are required.")
    if date.fromisoformat(record_date).isoformat() != record_date:
        raise ValueError("Record date must use YYYY-MM-DD.")

    if source.casefold() == "migraine diary" or (
        record_type is not None and record_type.strip().casefold() == "migraine_diary"
    ):
        raise ValueError(
            "Use save_migraine_entry to log or update a migraine diary entry."
        )

    metadata = {**patient_filter, "date": record_date, "source": source}
    if record_type is not None:
        record_type = record_type.strip().lower()
        if not record_type:
            raise ValueError("Record type must contain text when provided.")
        metadata["record_type"] = record_type
    collection.add(ids=[record_id], documents=[text], metadatas=[metadata])

    stored = collection.get(ids=[record_id], include=["documents", "metadatas"])
    if stored["documents"] != [text] or stored["metadatas"] != [metadata]:
        raise ValueError("This record ID already belongs to a different record.")

    return format_records(stored["ids"], stored["documents"], stored["metadatas"])[0]


@mcp.tool()
def save_migraine_entry(
    record_id: str | None = None,
    attack_date: str | None = None,
    start_time: str | None = None,
    severity: int | None = None,
    medication: str | None = None,
    regular_medications: list[str] | None = None,
    duration: str | None = None,
    ongoing: bool | None = None,
    other_symptoms: str | None = None,
    repeat_dose: str | None = None,
    possible_triggers: str | None = None,
    menstrual_timing: str | None = None,
    medication_changes: str | None = None,
    side_effects: str | None = None,
    comments: str | None = None,
    ask_optional: bool | None = None,
    skip_field: str | None = None,
) -> dict:
    """Log or update a migraine or headache diary entry.

    Save only details the user reported. On creation, the attack date is
    left unknown. Ask the returned next_question and wait for the user to
    answer. Then use the returned record_id to update the same entry with
    the date the user supplied. If they gave a date up front, ask them to
    confirm it before updating.

    Set regular_medications only after the user confirms the list applied
    at the time of this attack. Use [] if they explicitly report none.

    Set ask_optional=True to start or resume the optional questionnaire.
    Set ask_optional=False only when the user explicitly asks to pause it.
    Omit ask_optional on ordinary answers to keep the entry's saved setting.
    If the user asks to skip an optional question, pass its field name
    as skip_field with the record ID. Use "None reported" for a text
    field only when the user explicitly reports none.
    """
    if record_id is None:
        attack_date = None

    if attack_date is not None:
        if date.fromisoformat(attack_date).isoformat() != attack_date:
            raise ValueError("Attack date must use YYYY-MM-DD.")
    if severity is not None and not 0 <= severity <= 10:
        raise ValueError("Severity must be between 0 and 10.")

    fields = {
        "attack_date": attack_date,
        "start_time": start_time.strip() if start_time else None,
        "severity": severity,
        "medication": medication.strip() if medication else None,
        "duration": duration.strip() if duration else None,
        "ongoing": ongoing,
        "other_symptoms": other_symptoms.strip() if other_symptoms else None,
        "repeat_dose": repeat_dose.strip() if repeat_dose else None,
        "possible_triggers": possible_triggers.strip() if possible_triggers else None,
        "menstrual_timing": menstrual_timing.strip() if menstrual_timing else None,
        "medication_changes": medication_changes.strip() if medication_changes else None,
        "side_effects": side_effects.strip() if side_effects else None,
        "comments": comments.strip() if comments else None,
    }
    supplied = {
        key: value for key, value in fields.items()
        if value is not None and value != ""
    }
    if regular_medications is not None:
        items = [item.strip() for item in regular_medications]
        if any(not item for item in items):
            raise ValueError("Each regular medication must contain text.")
        supplied["regular_medications"] = json.dumps(items, ensure_ascii=False)

    optional_questions = {
        "ongoing": "Is the headache still ongoing?",
        "duration": "About how long did the headache last?",
        "other_symptoms": "Did you notice any other symptoms?",
        "medication": "Did you take anything for this headache? If so, what and when?",
        "repeat_dose": "Did you take another dose? If so, what and when?",
        "regular_medications": "What regular or preventive medications, if any, were you taking at the time?",
        "possible_triggers": "Any possible triggers you want to record?",
        "menstrual_timing": "If relevant, would you like to record menstrual timing?",
        "medication_changes": "Any recent medication changes you want to record?",
        "side_effects": "Any side effects you want to record?",
        "comments": "Anything else you want to record?",
    }
    if skip_field is not None:
        if record_id is None or skip_field not in optional_questions:
            raise ValueError("Specify an existing record ID and an optional field to skip.")
        if skip_field in supplied:
            raise ValueError("Give an answer or skip the field in this call.")
    if not supplied and skip_field is None and not (
        record_id and ask_optional is not None
    ):
        raise ValueError("Provide at least one reported detail.")

    if record_id is None:
        record_id = f"migraine_{uuid4().hex}"
        metadata = {
            **patient_filter,
            "source": "Migraine diary",
            "record_type": "migraine_diary",
            "log_date": date.today().isoformat(),
        }
        write = collection.add
    else:
        record_id = record_id.strip()
        stored = collection.get(
            ids=[record_id], where=patient_filter, include=["metadatas"]
        )
        if not stored["ids"] or stored["metadatas"][0].get("record_type") != "migraine_diary":
            raise ValueError("No migraine diary entry exists with that ID.")
        metadata = dict(stored["metadatas"][0])
        write = collection.update

    if skip_field is not None:
        if skip_field in metadata:
            raise ValueError("This field already has an answer.")
        metadata[f"skipped_{skip_field}"] = True
    for field in supplied.keys() & optional_questions.keys():
        if metadata.get(f"skipped_{field}"):
            metadata[f"skipped_{field}"] = False
    if ask_optional is not None:
        metadata["optional_questionnaire_enabled"] = ask_optional
    optional_enabled = metadata.get("optional_questionnaire_enabled", False)
    metadata.update(supplied)
    metadata["date"] = metadata.get("attack_date", metadata["log_date"])
    questions = {
        "attack_date": "What date did the headache start?",
        "start_time": "About what time did it start?",
        "severity": "How severe was it on a scale from 0 to 10?",
    }
    missing = [key for key in questions if key not in metadata]
    metadata["status"] = "partial" if missing else "complete"

    lines = [f"Log date: {metadata['log_date']}"]
    if metadata.get("attack_date"):
        weekday = date.fromisoformat(metadata["attack_date"]).strftime("%A")
        lines.append(f"Day of the week: {weekday}")
    for key, label in (
        ("attack_date", "Attack date"),
        ("start_time", "Start time"),
        ("severity", "Severity (0–10)"),
        ("medication", "Medication as reported"),
        ("duration", "Duration as reported"),
        ("ongoing", "Ongoing"),
        ("other_symptoms", "Other symptoms as reported"),
        ("repeat_dose", "Repeat dose as reported"),
        ("possible_triggers", "Possible triggers as reported"),
        ("menstrual_timing", "Menstrual timing as reported"),
        ("medication_changes", "Medication changes as reported"),
        ("side_effects", "Side effects as reported"),
        ("comments", "Comments"),
    ):
        value = metadata.get(
            key, "Skipped" if metadata.get(f"skipped_{key}") else "Unknown"
        )
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        lines.append(f"{label}: {value}")

    if "regular_medications" in metadata:
        items = json.loads(metadata["regular_medications"])
        reported = "; ".join(items) if items else "None reported"
    else:
        reported = "Skipped" if metadata.get("skipped_regular_medications") else "Unknown"
    lines.append(f"Regular medications at time of attack: {reported}")

    write(ids=[record_id], documents=["\n".join(lines)], metadatas=[metadata])

    next_field = missing[0] if missing else None
    next_question = questions[next_field] if next_field else None
    if next_field is None and optional_enabled:
        next_field = next(
            (
                field for field in optional_questions
                if field not in metadata
                and not metadata.get(f"skipped_{field}")
                and (field != "duration" or metadata.get("ongoing") is not True)
            ),
            None,
        )
        next_question = optional_questions.get(next_field)

    reply_instruction = (
        "Ask next_question in your reply and end this turn. "
        "Wait for the user's answer before calling save_migraine_entry again."
    )
    if next_field == "attack_date":
        reply_instruction += " Keep the log date separate from the attack date."
    elif next_field in optional_questions:
        reply_instruction += " Save a skip only if the user explicitly asks to skip this question."

    return {
        "record_id": record_id,
        "status": metadata["status"],
        "attack_date": metadata.get("attack_date"),
        "log_date": metadata["log_date"],
        "missing_fields": missing,
        "next_field": next_field,
        "next_question": next_question,
        "reply_instruction": (
            reply_instruction if next_question is not None
            else (
                "Summarize the saved entry and end without asking a question. "
                + (
                    "Tell the user the optional questionnaire is finished."
                    if optional_enabled
                    else 'Say: Optional questionnaire is off by default. To start it '
                         'for this entry, type "Continue the optional questions for this entry" in chat.'
                )
            )
        ),
    }


@mcp.tool()
def find_migraine_entries(
    attack_date: str | None = None,
    log_date: str | None = None,
) -> dict:
    """Find migraine entries by the date they started or were logged.

    Resolve relative dates using the user's local date before calling.
    Ask which date they mean if the wording is ambiguous. Use YYYY-MM-DD.
    If both filters are supplied, both must match. If several entries
    match, show their start times and ask the user to choose before editing.
    """
    dates = {"attack_date": attack_date, "log_date": log_date}
    if all(value is None for value in dates.values()):
        raise ValueError("Provide an attack date or a log date.")

    filters = [
        patient_filter,
        {"record_type": "migraine_diary"},
    ]
    for field, value in dates.items():
        if value is None:
            continue
        try:
            parsed = date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"{field} must use YYYY-MM-DD.") from error
        if parsed.isoformat() != value:
            raise ValueError(f"{field} must use YYYY-MM-DD.")
        filters.append({field: value})

    results = collection.get(where={"$and": filters}, include=["metadatas"])
    matches = [
        {
            "record_id": record_id,
            "attack_date": metadata.get("attack_date"),
            "log_date": metadata.get("log_date"),
            "start_time": metadata.get("start_time"),
            "severity": metadata.get("severity"),
        }
        for record_id, metadata in zip(results["ids"], results["metadatas"])
    ]
    matches.sort(key=lambda entry: (
        entry["attack_date"] or "",
        entry["log_date"] or "",
        entry["record_id"],
    ))
    result = {"matches": matches, "match_count": len(matches)}
    if len(matches) > 1:
        result["reply_instruction"] = (
            "Show the candidates with their start time, severity, log date, "
            "and record ID suffix. Ask the user to pick one and end this turn. "
            "Wait for their choice before opening any candidate or calling "
            "save_migraine_entry. Do not choose based on completeness."
        )
    return result


@mcp.tool()
def get_health_record(record_id: str) -> dict[str, str] | None:
    """Return one saved record by ID, including its full text, date, and source."""
    record_id = record_id.strip()
    if not record_id:
        raise ValueError("Record ID is required.")

    result = collection.get(
        ids=[record_id],
        where=patient_filter,
        include=["documents", "metadatas"],
    )
    records = format_records(
        result["ids"], result["documents"], result["metadatas"]
    )
    return records[0] if records else None



@mcp.tool()
def get_medication_profile() -> list[str] | None:
    """Read the user's current self-reported regular or preventive medications.

    None means no profile has been saved. An empty list means the user
    explicitly reported no regular or preventive medications.
    """
    profile_path = Path(collection_path_for_medication_profile())
    if not profile_path.exists():
        return None
    return json.loads(profile_path.read_text(encoding="utf-8"))


@mcp.tool()
def save_medication_profile(medications: list[str]) -> list[str]:
    """Replace the current list after the user confirms the full list.

    Preserve medication details as reported. Use an empty list only when
    the user explicitly reports taking no regular or preventive medication.
    """
    items = [item.strip() for item in medications]
    if any(not item for item in items):
        raise ValueError("Each medication entry must contain text.")

    profile_path = collection_path_for_medication_profile()
    with TemporaryDirectory(dir=profile_path.parent) as staging:
        pending = Path(staging) / profile_path.name
        pending.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        pending.replace(profile_path)
    return items


def collection_path_for_medication_profile() -> Path:
    return database_path / "medication_profile.json"


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
