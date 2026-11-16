import os
from datetime import date
from pathlib import Path
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
) -> dict:
    """Log or update a migraine or headache diary entry.

    Save only details the user reported. On creation, the attack date is
    left unknown. Ask the returned next_question and wait for the user to
    answer. Then use the returned record_id to update the same entry with
    the date the user supplied. If they gave a date up front, ask them to
    confirm it before updating.
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
    }
    supplied = {
        key: value for key, value in fields.items()
        if value is not None and value != ""
    }
    if not supplied:
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
    for key, label in (
        ("attack_date", "Attack date"),
        ("start_time", "Start time"),
        ("severity", "Severity (0–10)"),
        ("medication", "Medication as reported"),
    ):
        lines.append(f"{label}: {metadata.get(key, 'Unknown')}")
    write(ids=[record_id], documents=["\\n".join(lines)], metadatas=[metadata])

    return {
        "record_id": record_id,
        "status": metadata["status"],
        "attack_date": metadata.get("attack_date"),
        "log_date": metadata["log_date"],
        "missing_fields": missing,
        "next_question": questions[missing[0]] if missing else None,
    }


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


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
