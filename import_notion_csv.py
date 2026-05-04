import csv
import json
from pathlib import Path

import app

CSV_PATH = Path(
    "/Users/arsamanbahrami/Desktop/Private & Shared 2/Feature Priority Framework/Projects Database - Template 2c05c9515b5b817c9e43c072b5feaa69.csv"
)


STATUS_MAP = {
    "Idea": "Idea",
    "Planning": "Planned",
    "In progress": "In progress",
    "Complete": "Shipped",
}

URGENCY_MAP = {
    "Future": 1,
    "Flexible": 2,
    "Important": 4,
}

VISION_MAP = {
    "Weak": 2,
    "Medium": 3,
    "Strong": 5,
}

TSHIRT_MAP = {
    "Small": 2,
    "Medium": 3,
}

TIME_ESTIMATE_MAP = {
    "Quick (1-7 days)": 2,
    "Medium (1-4 weeks)": 3,
    "Long (1-3 months)": 5,
}

SOURCE_SPLIT = ","


def normalize_title(value):
    return " ".join((value or "").split()).strip().lower()


def parse_sources(raw_value):
    if not raw_value.strip():
        return ["Internal request"]
    return [part.strip() for part in raw_value.split(SOURCE_SPLIT) if part.strip()]


def to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def map_effort(row):
    t_shirt = (row.get("T-shirt Size") or "").strip()
    time_estimate = (row.get("Time Estimate") or "").strip()
    if t_shirt in TSHIRT_MAP:
        return TSHIRT_MAP[t_shirt]
    if time_estimate in TIME_ESTIMATE_MAP:
        return TIME_ESTIMATE_MAP[time_estimate]
    return 3


def map_dependency_risk(row):
    raw = (row.get("Dependencies") or "").strip()
    if raw == "0" or raw == "":
        return 1
    if raw == "1-2":
        return 3
    return 2


def build_notes(row):
    meta = {
        "original_created": (row.get("Created") or "").strip(),
        "original_priority_score": (row.get("Priority Score") or "").strip(),
        "original_product_vision_match": (row.get("Product Vision Match") or "").strip(),
        "original_t_shirt_size": (row.get("T-shirt Size") or "").strip(),
        "original_time_estimate": (row.get("Time Estimate") or "").strip(),
    }
    lines = [f"{key}: {value}" for key, value in meta.items() if value]
    return "\n".join(lines)


def make_payload(row):
    urgency_text = (row.get("Urgency") or "").strip()
    vision_text = (row.get("Product Vision Match") or "").strip()
    feature_title = " ".join((row.get("feature") or "").split()).strip()

    return {
        "title": feature_title,
        "problem_statement": (row.get("Description") or "").strip() or feature_title,
        "product_area": (row.get("Module") or "").strip() or "General",
        "status": STATUS_MAP.get((row.get("Status") or "").strip(), "Idea"),
        "request_sources": parse_sources((row.get("Source") or "").strip()),
        "team_owner": "",
        "submitted_by": "",
        "urgency_reason": (row.get("Urgency Reason") or "").strip(),
        "notes": build_notes(row),
        "dependencies": (row.get("Dependencies") or "").strip(),
        "quick_win": ((row.get("Quick Win") or "").strip().lower() == "yes"),
        "customer_impact": max(1, min(5, to_int(row.get("Priority Score"), 3) // 2 + 1)),
        "strategic_fit": VISION_MAP.get(vision_text, 3),
        "urgency": URGENCY_MAP.get(urgency_text, 2),
        "confidence": 3,
        "effort": map_effort(row),
        "dependency_risk": map_dependency_risk(row),
    }


def main():
    app.init_db()
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    existing = {normalize_title(feature["title"]) for feature in app.list_features()}
    imported = []
    skipped = []

    for row in rows:
        title_key = normalize_title(row.get("feature"))
        if not title_key:
            skipped.append({"title": "", "reason": "missing title"})
            continue
        if title_key in existing:
            skipped.append({"title": row.get("feature", "").strip(), "reason": "already exists"})
            continue

        payload = make_payload(row)
        app.create_feature(payload)
        existing.add(title_key)
        imported.append(payload["title"])

    print(json.dumps({"imported_count": len(imported), "skipped_count": len(skipped)}, ensure_ascii=False))
    if skipped:
        print(json.dumps(skipped, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
