"""Run the final Hey Joey MSc extraction, retrieval and abstention experiments."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Iterable

import xml.etree.ElementTree as ET
from zipfile import ZipFile


# Resolve paths from this script so the submitted repository is self-contained.
# ``PROJECT_ROOT`` points to Chatbot_Joey/, while the fixed thesis inputs and
# generated outputs stay beside this runner under evaluation/final_thesis/.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
DATA_DIR = SCRIPT_DIR / "data"
OUTPUT_DIR = SCRIPT_DIR / "results"

# Fail early if the runner has been moved outside the expected repository
# layout, because the experiment imports application and retrieval modules
# directly from the project root.
if not PROJECT_ROOT.exists():
    raise SystemExit(
        f"Chatbot_Joey project not found at: {PROJECT_ROOT}"
    )

# Allow direct execution of this file while still importing project modules
# such as app.extractor and rag.hybrid_retriever from the submitted repository.
sys.path.insert(0, str(PROJECT_ROOT))

# Resolve the experiment dependencies from the project code used by the thesis.
# Keeping these imports explicit makes it clear which implementation is being
# evaluated without duplicating the application logic inside this script.
extract_structured_record = getattr(
    import_module("app.extractor"),
    "extract_structured_record",
)
HybridStrategyRetriever = getattr(
    import_module("rag.hybrid_retriever"),
    "HybridStrategyRetriever",
)
build_retrieval_query = getattr(
    import_module("rag.joey_strategy_service"),
    "build_retrieval_query",
)
assess_retrieval_confidence = getattr(
    import_module("rag.retrieval_confidence"),
    "assess_retrieval_confidence",
)
retrieve_strategies = getattr(
    import_module("rag.strategy_retriever"),
    "retrieve_strategies",
)


# All retrieval metrics in the final thesis use the first three ranked items.
TOP_K = 3


# Convert arbitrary result metadata to a comparable lowercase token string.
# This helper is used only for deterministic evaluation matching.
def normalise_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, dict):
        return normalise_text(list(value.values()))

    if isinstance(value, (list, tuple, set)):
        value = " ".join(normalise_text(item) for item in value)

    import re

    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


# Return the one-based rank of the first result whose descriptor contains an
# expected keyword. ``None`` represents a miss within the evaluated top-k list.
def first_relevant_rank(
    descriptors: list[str],
    expected_keywords: list[str],
) -> int | None:
    keywords = [
        normalise_text(keyword)
        for keyword in expected_keywords
        if normalise_text(keyword)
    ]

    for rank, descriptor in enumerate(descriptors, start=1):
        if any(keyword in descriptor for keyword in keywords):
            return rank

    return None


# Build a searchable descriptor from BM25, semantic or hybrid result metadata.
def vector_descriptor(result: Any) -> str:
    return normalise_text(
        [
            getattr(result, "strategy_code", None),
            getattr(result, "strategy_title", None),
            getattr(result, "collection_title", None),
            getattr(result, "theme", None),
            getattr(result, "source_file", None),
        ]
    )


# Produce a compact human-readable label for vector-retrieval result output.
def vector_label(result: Any) -> str:
    code = getattr(result, "strategy_code", None)
    title = getattr(result, "strategy_title", None)
    collection = getattr(result, "collection_title", None)

    if code and title:
        return f"{code}: {title}"

    return str(title or collection or "Unnamed strategy")


# Normalise the older rule-based baseline result shape for the same relevance
# check used by the BM25, semantic and hybrid methods.
def baseline_descriptor(result: Any) -> str:
    if not isinstance(result, dict):
        return normalise_text(result)

    preferred_fields = [
        "title",
        "name",
        "category",
        "strategy_category",
        "collection_title",
        "source",
        "source_file",
    ]
    values = [
        result.get(field)
        for field in preferred_fields
        if result.get(field)
    ]

    return normalise_text(values if values else result)


# Produce a readable title for the rule-based baseline results.
def baseline_label(result: Any) -> str:
    if isinstance(result, dict):
        for field in ("title", "name", "category", "strategy_category"):
            if result.get(field):
                return str(result[field])

    return str(result)


# Write matrix-style CSV output while creating the parent directory when needed.
def write_csv(
    path: Path,
    headers: list[str],
    rows: Iterable[Iterable[Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(rows)


# Write dictionaries using the first row as the stable CSV column order.
def write_dict_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        raise ValueError(f"No rows were available for {path.name}.")

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


# Avoid division-by-zero failures when a class or decision subset is empty.
def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


# Calculate per-class, macro and weighted metrics plus a confusion matrix for
# the project-defined multiclass extraction labels.
def classification_metrics(
    expected: list[str],
    predicted: list[str],
) -> tuple[dict[str, float], list[dict[str, Any]], list[list[Any]]]:
    labels = sorted(set(expected) | set(predicted))
    total = len(expected)
    correct = sum(a == b for a, b in zip(expected, predicted))

    class_rows: list[dict[str, Any]] = []
    supports: dict[str, int] = {}

    for label in labels:
        tp = sum(
            actual == label and guess == label
            for actual, guess in zip(expected, predicted)
        )
        fp = sum(
            actual != label and guess == label
            for actual, guess in zip(expected, predicted)
        )
        fn = sum(
            actual == label and guess != label
            for actual, guess in zip(expected, predicted)
        )
        support = sum(actual == label for actual in expected)
        supports[label] = support

        precision = safe_divide(tp, tp + fp)
        recall = safe_divide(tp, tp + fn)
        f1 = safe_divide(2 * precision * recall, precision + recall)

        class_rows.append(
            {
                "class": label,
                "support": support,
                "true_positive": tp,
                "false_positive": fp,
                "false_negative": fn,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
            }
        )

    macro_precision = statistics.mean(
        row["precision"] for row in class_rows
    )
    macro_recall = statistics.mean(
        row["recall"] for row in class_rows
    )
    macro_f1 = statistics.mean(
        row["f1"] for row in class_rows
    )
    weighted_f1 = safe_divide(
        sum(row["f1"] * supports[row["class"]] for row in class_rows),
        total,
    )

    summary = {
        "accuracy": round(safe_divide(correct, total), 4),
        "macro_precision": round(macro_precision, 4),
        "macro_recall": round(macro_recall, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
    }

    matrix: list[list[Any]] = [["expected\\predicted", *labels]]

    for actual_label in labels:
        counts = [
            sum(
                actual == actual_label and guess == predicted_label
                for actual, guess in zip(expected, predicted)
            )
            for predicted_label in labels
        ]
        matrix_row: list[Any] = [actual_label]
        matrix_row.extend(counts)
        matrix.append(matrix_row)

    return summary, class_rows, matrix


# Calculate accuracy, precision, recall and F1 for the binary safety outcome.
def binary_metrics(
    expected: list[bool],
    predicted: list[bool],
) -> dict[str, float]:
    tp = sum(a and p for a, p in zip(expected, predicted))
    tn = sum((not a) and (not p) for a, p in zip(expected, predicted))
    fp = sum((not a) and p for a, p in zip(expected, predicted))
    fn = sum(a and (not p) for a, p in zip(expected, predicted))

    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    f1 = safe_divide(2 * precision * recall, precision + recall)

    return {
        "accuracy": round(safe_divide(tp + tn, len(expected)), 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
    }


# Convert an Excel cell reference such as "AB12" into a zero-based column index.
def column_index(cell_reference: str) -> int:
    letters = "".join(
        character
        for character in cell_reference
        if character.isalpha()
    )

    index = 0

    for character in letters.upper():
        index = index * 26 + (ord(character) - ord("A") + 1)

    return index - 1


# Read rows directly from an XLSX ZIP/XML package. This keeps the final runner
# independent of pandas/openpyxl for the approved hold-out workbook check.
def xlsx_sheet_rows(
    workbook_path: Path,
    sheet_name: str,
) -> list[list[Any]]:
    spreadsheet_namespace = (
        "http://schemas.openxmlformats.org/"
        "spreadsheetml/2006/main"
    )
    relationship_namespace = (
        "http://schemas.openxmlformats.org/"
        "officeDocument/2006/relationships"
    )
    package_relationship_namespace = (
        "http://schemas.openxmlformats.org/"
        "package/2006/relationships"
    )

    with ZipFile(workbook_path) as archive:
        workbook_root = ET.fromstring(
            archive.read("xl/workbook.xml")
        )
        relationship_root = ET.fromstring(
            archive.read("xl/_rels/workbook.xml.rels")
        )

        relationship_targets = {
            relationship.attrib["Id"]: relationship.attrib["Target"]
            for relationship in relationship_root.findall(
                f"{{{package_relationship_namespace}}}Relationship"
            )
        }

        sheet_relationship_id: str | None = None

        for sheet in workbook_root.findall(
            f".//{{{spreadsheet_namespace}}}sheet"
        ):
            if sheet.attrib.get("name") == sheet_name:
                sheet_relationship_id = sheet.attrib.get(
                    f"{{{relationship_namespace}}}id"
                )
                break

        if not sheet_relationship_id:
            raise ValueError(
                f"Workbook does not contain sheet: {sheet_name}"
            )

        target = relationship_targets[sheet_relationship_id].lstrip("/")

        if not target.startswith("xl/"):
            target = f"xl/{target}"

        shared_strings: list[str] = []

        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(
                archive.read("xl/sharedStrings.xml")
            )

            for item in shared_root.findall(
                f"{{{spreadsheet_namespace}}}si"
            ):
                shared_strings.append(
                    "".join(
                        node.text or ""
                        for node in item.iter(
                            f"{{{spreadsheet_namespace}}}t"
                        )
                    )
                )

        sheet_root = ET.fromstring(archive.read(target))
        rows: list[list[Any]] = []

        for row_node in sheet_root.findall(
            f".//{{{spreadsheet_namespace}}}row"
        ):
            excel_row_number = int(row_node.attrib.get("r", "0"))
            row_values: list[Any] = []

            for cell in row_node.findall(
                f"{{{spreadsheet_namespace}}}c"
            ):
                reference = cell.attrib.get("r", "")
                index = column_index(reference)

                while len(row_values) <= index:
                    row_values.append("")

                cell_type = cell.attrib.get("t")
                value_node = cell.find(
                    f"{{{spreadsheet_namespace}}}v"
                )

                if cell_type == "inlineStr":
                    inline_node = cell.find(
                        f"{{{spreadsheet_namespace}}}is"
                    )
                    value: Any = (
                        "".join(
                            node.text or ""
                            for node in inline_node.iter(
                                f"{{{spreadsheet_namespace}}}t"
                            )
                        )
                        if inline_node is not None
                        else ""
                    )
                elif value_node is None:
                    value = ""
                elif cell_type == "s":
                    value = shared_strings[int(value_node.text or "0")]
                elif cell_type == "b":
                    value = value_node.text == "1"
                else:
                    value = value_node.text or ""

                row_values[index] = value

            while len(rows) < excel_row_number:
                rows.append([])

            rows[excel_row_number - 1] = row_values

    return rows


# Convert worksheet rows into dictionaries keyed by the first-row headers.
def xlsx_sheet_records(
    workbook_path: Path,
    sheet_name: str,
) -> list[dict[str, Any]]:
    rows = xlsx_sheet_rows(workbook_path, sheet_name)

    if not rows:
        return []

    headers = [str(value).strip() for value in rows[0]]
    records: list[dict[str, Any]] = []

    for row in rows[1:]:
        if not any(str(value).strip() for value in row):
            continue

        record = {
            header: row[index] if index < len(row) else ""
            for index, header in enumerate(headers)
            if header
        }
        records.append(record)

    return records


# Read the approval flag from the workbook Instructions sheet so the frozen
# extraction hold-out cannot be evaluated accidentally while still marked DRAFT.
def read_holdout_status(workbook_path: Path) -> str:
    rows = xlsx_sheet_rows(workbook_path, "Instructions")

    for row in rows:
        if not row:
            continue

        label = str(row[0] or "").strip().casefold()

        if label == "dataset status":
            status = (
                str(row[1] or "").strip().upper()
                if len(row) > 1
                else ""
            )

            print(
                "Hold-out workbook status: "
                f"{status or '[blank]'}"
            )
            print(f"Workbook path: {workbook_path}")
            return status

    raise ValueError(
        "The Instructions sheet does not contain a Dataset status row."
    )


# Run deterministic extraction over the frozen 30-case hold-out workbook and
# write the case-level predictions, class metrics and confusion matrices.
def run_extraction_experiment() -> dict[str, Any]:
    # The workbook contains the reviewed labels and an explicit APPROVED status.
    workbook_path = DATA_DIR / "holdout_extraction_dataset.xlsx"

    status = read_holdout_status(workbook_path)

    # Refuse to run if the evaluation labels have not been explicitly frozen.
    if status != "APPROVED":
        raise RuntimeError(
            "The hold-out workbook is still DRAFT. "
            "Review every label and change Instructions!B3 to APPROVED."
        )

    # Load the fixed hold-out rows only after the approval check succeeds.
    cases = xlsx_sheet_records(
        workbook_path,
        "Holdout_Cases",
    )

    required_columns = {
        "case_id",
        "note",
        "expected_anxiety",
        "expected_mood_zone",
        "expected_safety",
    }

    available_columns = set(cases[0]) if cases else set()
    missing = required_columns.difference(available_columns)

    if missing:
        raise ValueError(
            "Hold-out workbook is missing columns: "
            + ", ".join(sorted(missing))
        )

    rows: list[dict[str, Any]] = []

    # Evaluate each observation independently using the production extractor.
    for case in cases:
        note = str(case["note"])
        record = extract_structured_record(note)

        expected_safety = (
            str(case["expected_safety"]).strip().lower() == "yes"
        )
        predicted_safety = bool(record.risk_flags)

        rows.append(
            {
                "case_id": str(case["case_id"]),
                "case_group": str(case.get("case_group", "")),
                "note": note,
                "expected_anxiety": str(case["expected_anxiety"]),
                "predicted_anxiety": record.anxiety_level.value,
                "anxiety_correct": (
                    str(case["expected_anxiety"])
                    == record.anxiety_level.value
                ),
                "expected_mood_zone": str(case["expected_mood_zone"]),
                "predicted_mood_zone": record.mood_zone.value,
                "mood_zone_correct": (
                    str(case["expected_mood_zone"])
                    == record.mood_zone.value
                ),
                "expected_safety": expected_safety,
                "predicted_safety": predicted_safety,
                "safety_correct": expected_safety == predicted_safety,
                "predicted_risk_flags": " | ".join(record.risk_flags),
                "all_three_correct": (
                    str(case["expected_anxiety"])
                    == record.anxiety_level.value
                    and str(case["expected_mood_zone"])
                    == record.mood_zone.value
                    and expected_safety == predicted_safety
                ),
            }
        )

    # Preserve case-level predictions first so every aggregate score is auditable.
    write_dict_csv(
        OUTPUT_DIR / "extraction_case_results.csv",
        rows,
    )

    expected_anxiety = [row["expected_anxiety"] for row in rows]
    predicted_anxiety = [row["predicted_anxiety"] for row in rows]
    expected_mood = [row["expected_mood_zone"] for row in rows]
    predicted_mood = [row["predicted_mood_zone"] for row in rows]
    expected_safety = [bool(row["expected_safety"]) for row in rows]
    predicted_safety = [bool(row["predicted_safety"]) for row in rows]

    # Compute the thesis metrics separately for anxiety, mood and safety.
    anxiety_summary, anxiety_classes, anxiety_matrix = (
        classification_metrics(
            expected_anxiety,
            predicted_anxiety,
        )
    )
    mood_summary, mood_classes, mood_matrix = classification_metrics(
        expected_mood,
        predicted_mood,
    )
    safety_summary = binary_metrics(
        expected_safety,
        predicted_safety,
    )

    # Store a compact summary table alongside the detailed class-level outputs.
    summary_rows = [
        {
            "field": "anxiety_level",
            **anxiety_summary,
        },
        {
            "field": "mood_zone",
            **mood_summary,
        },
        {
            "field": "safety_flag",
            "accuracy": safety_summary["accuracy"],
            "macro_precision": safety_summary["precision"],
            "macro_recall": safety_summary["recall"],
            "macro_f1": safety_summary["f1"],
            "weighted_f1": safety_summary["f1"],
        },
        {
            "field": "exact_all_three",
            "accuracy": round(
                safe_divide(
                    sum(bool(row["all_three_correct"]) for row in rows),
                    len(rows),
                ),
                4,
            ),
            "macro_precision": "",
            "macro_recall": "",
            "macro_f1": "",
            "weighted_f1": "",
        },
    ]

    write_dict_csv(
        OUTPUT_DIR / "extraction_summary.csv",
        summary_rows,
    )
    write_dict_csv(
        OUTPUT_DIR / "extraction_anxiety_class_metrics.csv",
        anxiety_classes,
    )
    write_dict_csv(
        OUTPUT_DIR / "extraction_mood_class_metrics.csv",
        mood_classes,
    )
    write_csv(
        OUTPUT_DIR / "extraction_anxiety_confusion_matrix.csv",
        anxiety_matrix[0],
        anxiety_matrix[1:],
    )
    write_csv(
        OUTPUT_DIR / "extraction_mood_confusion_matrix.csv",
        mood_matrix[0],
        mood_matrix[1:],
    )
    write_dict_csv(
        OUTPUT_DIR / "extraction_safety_metrics.csv",
        [safety_summary],
    )

    print("\nHOLD-OUT EXTRACTION EVALUATION")
    print("=" * 72)
    print(f"Cases: {len(rows)}")
    print(
        "Anxiety accuracy: "
        f"{anxiety_summary['accuracy']:.1%} "
        f"| macro F1: {anxiety_summary['macro_f1']:.4f}"
    )
    print(
        "Mood-zone accuracy: "
        f"{mood_summary['accuracy']:.1%} "
        f"| macro F1: {mood_summary['macro_f1']:.4f}"
    )
    print(
        "Safety accuracy: "
        f"{safety_summary['accuracy']:.1%} "
        f"| F1: {safety_summary['f1']:.4f}"
    )
    print(
        "Exact all-three accuracy: "
        f"{summary_rows[-1]['accuracy']:.1%}"
    )

    return {
        "case_count": len(rows),
        "anxiety": anxiety_summary,
        "mood_zone": mood_summary,
        "safety": safety_summary,
        "exact_all_three_accuracy": summary_rows[-1]["accuracy"],
    }


# Summarise one retrieval method using Hit@1, Hit@3, MRR and warm-run latency.
def method_summary(
    rows: list[dict[str, Any]],
    prefix: str,
) -> dict[str, Any]:
    ranks = [row[f"{prefix}_rank"] for row in rows]
    latencies = [float(row[f"{prefix}_latency_ms"]) for row in rows]

    hit1 = sum(rank == 1 for rank in ranks)
    hit3 = sum(rank is not None and rank <= TOP_K for rank in ranks)
    reciprocal_ranks = [
        1.0 / rank if rank is not None else 0.0
        for rank in ranks
    ]

    return {
        "method": prefix,
        "queries": len(rows),
        "hit_at_1": hit1,
        "hit_at_1_rate": round(safe_divide(hit1, len(rows)), 4),
        "hit_at_3": hit3,
        "hit_at_3_rate": round(safe_divide(hit3, len(rows)), 4),
        "mrr": round(statistics.mean(reciprocal_ranks), 4),
        "mean_latency_ms": round(statistics.mean(latencies), 3),
        "median_latency_ms": round(statistics.median(latencies), 3),
        "stdev_latency_ms": round(
            statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
            3,
        ),
    }


# Compare the rule-based, BM25-only, semantic-only and Hybrid RRF methods on
# the same fixed 30-query dataset used in the final dissertation.
def run_retrieval_experiment(
    retriever: Any,
) -> dict[str, Any]:
    # Read the frozen retrieval cases from the submitted thesis-data directory.
    cases = json.loads(
        (DATA_DIR / "retrieval_final_cases.json").read_text(
            encoding="utf-8"
        )
    )

    # Warm the local lexical/semantic components before latency measurement so
    # model/index startup cost does not dominate the per-query comparison.
    warmup = (
        "child overwhelmed by loud classroom noise "
        "and covering their ears"
    )
    retriever.semantic.search(
        query=warmup,
        top_k=TOP_K,
        strategy_only=True,
        deduplicate_strategies=True,
    )
    retriever.lexical.search(
        query=warmup,
        top_k=TOP_K,
        strategy_only=True,
        deduplicate_strategies=True,
    )
    retriever.search(
        query=warmup,
        top_k=TOP_K,
        strategy_only=True,
    )

    rows: list[dict[str, Any]] = []

    # Run all four methods on exactly the same query and expected collection.
    for case in cases:
        query = str(case["query"])
        expected_keywords = list(case["expected_keywords"])

        # Build the same privacy-reduced retrieval query used by the Joey service.
        record = extract_structured_record(query)
        retrieval_query = build_retrieval_query(
            record,
            original_note=query,
        )

        # Time each method independently while keeping TOP_K constant.
        started = time.perf_counter()
        baseline_results = list(
            retrieve_strategies(
                record,
                original_note=query,
                top_k=TOP_K,
            )
        )[:TOP_K]
        baseline_ms = (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        bm25_results = retriever.lexical.search(
            query=retrieval_query,
            top_k=TOP_K,
            strategy_only=True,
            deduplicate_strategies=True,
        )
        bm25_ms = (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        semantic_results = retriever.semantic.search(
            query=retrieval_query,
            top_k=TOP_K,
            strategy_only=True,
            deduplicate_strategies=True,
        )
        semantic_ms = (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        hybrid_results = retriever.search(
            query=retrieval_query,
            top_k=TOP_K,
            strategy_only=True,
        )
        hybrid_ms = (time.perf_counter() - started) * 1000

        # Convert returned metadata into comparable descriptors and record the
        # first expected match for ranking metrics.
        baseline_rank = first_relevant_rank(
            [baseline_descriptor(item) for item in baseline_results],
            expected_keywords,
        )
        bm25_rank = first_relevant_rank(
            [vector_descriptor(item) for item in bm25_results],
            expected_keywords,
        )
        semantic_rank = first_relevant_rank(
            [vector_descriptor(item) for item in semantic_results],
            expected_keywords,
        )
        hybrid_rank = first_relevant_rank(
            [vector_descriptor(item) for item in hybrid_results],
            expected_keywords,
        )

        rows.append(
            {
                "case_id": case["case_id"],
                "collection_group": case["collection_group"],
                "query_style": case["query_style"],
                "query": query,
                "expected_keywords": " | ".join(expected_keywords),
                "baseline_rank": baseline_rank,
                "bm25_rank": bm25_rank,
                "semantic_rank": semantic_rank,
                "hybrid_rank": hybrid_rank,
                "baseline_latency_ms": round(baseline_ms, 3),
                "bm25_latency_ms": round(bm25_ms, 3),
                "semantic_latency_ms": round(semantic_ms, 3),
                "hybrid_latency_ms": round(hybrid_ms, 3),
                "baseline_titles": " | ".join(
                    baseline_label(item) for item in baseline_results
                ),
                "bm25_titles": " | ".join(
                    vector_label(item) for item in bm25_results
                ),
                "semantic_titles": " | ".join(
                    vector_label(item) for item in semantic_results
                ),
                "hybrid_titles": " | ".join(
                    vector_label(item) for item in hybrid_results
                ),
            }
        )

        print(
            f"[retrieval] {case['case_id']} "
            f"baseline={baseline_rank} bm25={bm25_rank} "
            f"semantic={semantic_rank} hybrid={hybrid_rank}"
        )

    # Save case-level rankings/latencies before computing aggregate summaries.
    write_dict_csv(
        OUTPUT_DIR / "retrieval_final_case_results.csv",
        rows,
    )

    # Aggregate each method independently for the final thesis comparison table.
    summaries = [
        method_summary(rows, "baseline"),
        method_summary(rows, "bm25"),
        method_summary(rows, "semantic"),
        method_summary(rows, "hybrid"),
    ]

    display_names = {
        "baseline": "Rule-based",
        "bm25": "BM25-only",
        "semantic": "Semantic-only",
        "hybrid": "Hybrid RRF",
    }

    for summary in summaries:
        summary["display_name"] = display_names[summary["method"]]

    write_dict_csv(
        OUTPUT_DIR / "retrieval_final_summary.csv",
        summaries,
    )

    (OUTPUT_DIR / "retrieval_final_results.json").write_text(
        json.dumps(
            {
                "top_k": TOP_K,
                "case_count": len(rows),
                "summaries": summaries,
                "results": rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nFOUR-METHOD RETRIEVAL EVALUATION")
    print("=" * 72)

    for summary in summaries:
        print(
            f"{summary['display_name']:<16} "
            f"Hit@1={summary['hit_at_1_rate']:.1%} "
            f"Hit@3={summary['hit_at_3_rate']:.1%} "
            f"MRR={summary['mrr']:.4f} "
            f"mean={summary['mean_latency_ms']:.3f} ms"
        )

    return {
        "case_count": len(rows),
        "summaries": summaries,
    }


# Minimal immutable evidence shape expected by the confidence assessor. The
# adapter below isolates the experiment from the retriever result dataclass.
@dataclass(frozen=True)
class ConfidenceEvidence:
    original_score: float
    strategy_code: str | None
    strategy_title: str | None
    collection_title: str
    source_file: str
    theme: str | None
    passage: str


# Convert hybrid retrieval results into the evidence fields used by confidence.
def adapt_evidence(
    results: list[Any],
) -> list[ConfidenceEvidence]:
    return [
        ConfidenceEvidence(
            original_score=result.score,
            strategy_code=result.strategy_code,
            strategy_title=result.strategy_title,
            collection_title=result.collection_title,
            source_file=result.source_file,
            theme=result.theme,
            passage=result.text,
        )
        for result in results
    ]


# Score one answer/abstain rule using coverage, selective accuracy and overall
# decision accuracy, while tracking correct and unnecessary abstentions.
def threshold_metrics(
    case_rows: list[dict[str, Any]],
    name: str,
    decide_answer,
) -> dict[str, Any]:
    answered = 0
    correct_answer = 0
    wrong_answer = 0
    correct_abstain = 0
    unnecessary_abstain = 0

    for row in case_rows:
        answer = bool(decide_answer(row))
        should_answer = bool(row["should_answer"])
        top_relevant = bool(row["top_relevant"])

        if answer:
            answered += 1

            if should_answer and top_relevant:
                correct_answer += 1
            else:
                wrong_answer += 1
        else:
            if should_answer:
                unnecessary_abstain += 1
            else:
                correct_abstain += 1

    should_abstain_count = sum(
        not bool(row["should_answer"])
        for row in case_rows
    )
    should_answer_count = len(case_rows) - should_abstain_count

    return {
        "configuration": name,
        "queries": len(case_rows),
        "answered": answered,
        "coverage": round(safe_divide(answered, len(case_rows)), 4),
        "selective_accuracy": round(
            safe_divide(correct_answer, answered),
            4,
        ),
        "overall_decision_accuracy": round(
            safe_divide(
                correct_answer + correct_abstain,
                len(case_rows),
            ),
            4,
        ),
        "correct_answers": correct_answer,
        "wrong_answers": wrong_answer,
        "correct_abstentions": correct_abstain,
        "unnecessary_abstentions": unnecessary_abstain,
        "correct_abstention_rate": round(
            safe_divide(correct_abstain, should_abstain_count),
            4,
        ),
        "unnecessary_abstention_rate": round(
            safe_divide(unnecessary_abstain, should_answer_count),
            4,
        ),
    }


# Evaluate the current confidence rule and a small threshold grid on the fixed
# 30-query answer-versus-abstain dataset used in the dissertation.
def run_confidence_experiment(
    retriever: Any,
) -> dict[str, Any]:
    # Load the frozen confidence cases from the submitted data directory.
    cases = json.loads(
        (DATA_DIR / "confidence_cases.json").read_text(
            encoding="utf-8"
        )
    )

    case_rows: list[dict[str, Any]] = []

    # Capture the current system decision and reusable evidence features once per
    # query so alternative thresholds can be compared without rerunning retrieval.
    for case in cases:
        query = str(case["query"])
        results = retriever.search(
            query=query,
            top_k=TOP_K,
            strategy_only=True,
        )
        evidence = adapt_evidence(results)
        decision = assess_retrieval_confidence(
            query,
            evidence,
        )

        rank = first_relevant_rank(
            [vector_descriptor(item) for item in results],
            list(case["expected_keywords"]),
        )

        row = {
            "case_id": case["case_id"],
            "group": case["group"],
            "query": query,
            "should_answer": bool(case["should_answer"]),
            "expected_keywords": " | ".join(case["expected_keywords"]),
            "top_relevant": rank == 1,
            "first_relevant_rank": rank,
            "current_level": decision.level.value,
            "current_should_abstain": decision.should_abstain,
            "query_token_count": decision.query_token_count,
            "evidence_count": decision.evidence_count,
            "top_original_score": decision.top_original_score,
            "top_overlap_count": decision.top_overlap_count,
            "top_overlap_ratio": decision.top_overlap_ratio,
            "overlapping_evidence_count": decision.overlapping_evidence_count,
            "top_result": vector_label(results[0]) if results else "",
            "top_collection": results[0].collection_title if results else "",
        }
        case_rows.append(row)

        print(
            f"[confidence] {case['case_id']} "
            f"expected={'answer' if case['should_answer'] else 'abstain'} "
            f"current={'abstain' if decision.should_abstain else 'answer'} "
            f"score={decision.top_original_score:.6f} "
            f"overlap={decision.top_overlap_count}"
        )

    # Persist the feature table that underpins every threshold comparison.
    write_dict_csv(
        OUTPUT_DIR / "confidence_case_features.csv",
        case_rows,
    )

    summaries: list[dict[str, Any]] = []

    # Evaluate the exact confidence behaviour currently used by the application.
    current = threshold_metrics(
        case_rows,
        "CURRENT_SYSTEM",
        lambda row: not bool(row["current_should_abstain"]),
    )
    current["minimum_overlap"] = ""
    current["minimum_score"] = ""
    summaries.append(current)

    # Sweep the small deterministic threshold grid reported in the thesis.
    for minimum_overlap in (0, 1, 2, 3):
        for minimum_score in (0.000, 0.019, 0.021, 0.024, 0.027):
            name = (
                f"overlap>={minimum_overlap};"
                f"score>={minimum_score:.3f}"
            )
            summary = threshold_metrics(
                case_rows,
                name,
                lambda row, overlap=minimum_overlap, score=minimum_score: (
                    int(row["query_token_count"]) >= 2
                    and int(row["top_overlap_count"]) >= overlap
                    and float(row["top_original_score"]) >= score
                ),
            )
            summary["minimum_overlap"] = minimum_overlap
            summary["minimum_score"] = minimum_score
            summaries.append(summary)

    # Keep the current system first, then order alternatives by decision quality.
    summaries.sort(
        key=lambda row: (
            row["configuration"] != "CURRENT_SYSTEM",
            -float(row["overall_decision_accuracy"]),
            -float(row["selective_accuracy"]),
            -float(row["coverage"]),
        )
    )

    write_dict_csv(
        OUTPUT_DIR / "confidence_threshold_summary.csv",
        summaries,
    )

    # Retain configurations that are not dominated on both coverage and
    # selective accuracy, providing a compact view of the trade-off frontier.
    pareto_rows: list[dict[str, Any]] = []

    for candidate in summaries:
        dominated = False

        for other in summaries:
            if other is candidate:
                continue

            at_least_as_good = (
                float(other["coverage"]) >= float(candidate["coverage"])
                and float(other["selective_accuracy"])
                >= float(candidate["selective_accuracy"])
            )
            strictly_better = (
                float(other["coverage"]) > float(candidate["coverage"])
                or float(other["selective_accuracy"])
                > float(candidate["selective_accuracy"])
            )

            if at_least_as_good and strictly_better:
                dominated = True
                break

        if not dominated:
            pareto_rows.append(candidate)

    write_dict_csv(
        OUTPUT_DIR / "confidence_pareto_frontier.csv",
        pareto_rows,
    )

    print("\nCONFIDENCE AND ABSTENTION ANALYSIS")
    print("=" * 72)
    print(
        "Current system: "
        f"coverage={current['coverage']:.1%} "
        f"selective accuracy={current['selective_accuracy']:.1%} "
        f"overall decision accuracy={current['overall_decision_accuracy']:.1%}"
    )
    print(
        "Threshold configurations evaluated: "
        f"{len(summaries)}"
    )

    return {
        "case_count": len(case_rows),
        "current_system": current,
        "pareto_frontier": pareto_rows,
    }


# Orchestrate any requested subset of the three final thesis experiments.
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Skip the approved hold-out extraction evaluation.",
    )
    parser.add_argument(
        "--skip-retrieval",
        action="store_true",
        help="Skip the four-method retrieval evaluation.",
    )
    parser.add_argument(
        "--skip-confidence",
        action="store_true",
        help="Skip the confidence-threshold analysis.",
    )
    arguments = parser.parse_args()

    # Ensure the repository-local results directory exists before any experiment
    # writes output. The manifest deliberately avoids machine-specific paths.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "project_root": ".",
        "thesis_root": None,
        "top_k": TOP_K,
        "experiments": {},
    }

    # Run only the experiment groups requested on the command line.
    if not arguments.skip_extraction:
        manifest["experiments"]["extraction"] = (
            run_extraction_experiment()
        )

    retriever: Any | None = None

    # BM25/semantic resources are loaded once and shared by retrieval and
    # confidence experiments to avoid unnecessary duplicate model startup.
    if (
        not arguments.skip_retrieval
        or not arguments.skip_confidence
    ):
        print("\nLoading the local semantic and BM25 retrievers...")
        retriever = HybridStrategyRetriever()

    if not arguments.skip_retrieval:
        assert retriever is not None
        manifest["experiments"]["retrieval"] = (
            run_retrieval_experiment(retriever)
        )

    if not arguments.skip_confidence:
        assert retriever is not None
        manifest["experiments"]["confidence"] = (
            run_confidence_experiment(retriever)
        )

    # Record completion time as run metadata; datasets and metric definitions are
    # fixed elsewhere in the manifest and result files.
    manifest["completed_at_local"] = time.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # Write one machine-independent manifest containing the reported summaries.
    (OUTPUT_DIR / "final_experiment_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nFINAL EXPERIMENTS COMPLETE")
    print("=" * 72)
    print(f"Outputs: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
