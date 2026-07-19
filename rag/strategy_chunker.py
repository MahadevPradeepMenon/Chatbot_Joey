import csv
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "strategies_text"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "strategy_chunks"
)

DOCUMENT_MANIFEST = (
    INPUT_DIR
    / "strategy_document_manifest.json"
)

OUTPUT_JSONL = OUTPUT_DIR / "strategy_chunks.jsonl"
OUTPUT_CSV = OUTPUT_DIR / "strategy_chunks.csv"
OUTPUT_MANIFEST = OUTPUT_DIR / "strategy_chunk_manifest.json"

# A chunk should be focused enough for retrieval but still contain
# enough context to understand the strategy.
MAX_CHARACTERS = 2200
OVERLAP_PARAGRAPHS = 1


def strip_heading_marks(text: str) -> str:
    """Remove Markdown heading markers produced by the document loader."""

    return re.sub(r"^#{1,6}\s*", "", text).strip()


def slugify(text: str) -> str:
    """Convert text into a safe identifier."""

    value = text.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")

    return value or "chunk"


def detect_theme(text: str) -> str | None:
    """
    Detect theme headings such as:

    Theme A: Understanding Eating Challenges
    A. Performance Anxiety Strategies
    """

    clean_text = strip_heading_marks(text)

    if re.match(
        r"^Theme\s+[A-Z]\s*[:.\-]",
        clean_text,
        flags=re.IGNORECASE,
    ):
        return clean_text

    if re.match(
        r"^[A-Z]\.\s+.+\bStrategies\b",
        clean_text,
        flags=re.IGNORECASE,
    ):
        return clean_text

    return None


def detect_strategy(text: str) -> tuple[str, str] | None:
    """
    Detect different strategy-title formats used in the real documents.

    Examples:

    Strategy A1: Title
    Strategy A2 :: Title
    Strategy A1 Title
    A1. Title
    """

    clean_text = strip_heading_marks(text)

    match = re.match(
        r"^(?:Strategy\s+)?"
        r"([A-Z]\d+)\b"
        r"\s*(?:::+|[:.\-])?\s*"
        r"(.+)$",
        clean_text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    strategy_code = match.group(1).upper()
    strategy_title = match.group(2).strip(" :-")

    if not strategy_title:
        return None

    return strategy_code, strategy_title


def looks_like_context_heading(text: str) -> bool:
    """
    Detect non-strategy headings such as introductions,
    implementation guides and safety notices.
    """

    clean_text = strip_heading_marks(text)

    if text.lstrip().startswith("#"):
        return True

    if len(clean_text) > 110:
        return False

    if clean_text.endswith((".", ";", ",")):
        return False

    common_heading_prefixes = (
        "Introduction",
        "Implementation Guide",
        "Key Principles",
        "When to Seek",
        "Troubleshooting",
        "Realistic Expectations",
        "What This Collection Offers",
        "Quick-Start",
        "Critical Safety",
        "Understanding the Professional Team",
        "Social Skills Teaching",
        "Individual and Cultural Differences",
        "Assessment",
        "Implementation Timeline",
    )

    return clean_text.startswith(common_heading_prefixes)


def split_long_paragraph(
    text: str,
    max_characters: int,
) -> list[str]:
    """Split a single oversized paragraph without cutting through words."""

    if len(text) <= max_characters:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)

    pieces: list[str] = []
    current_piece = ""

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        # Fall back to word-based splitting if one sentence is extremely long.
        if len(sentence) > max_characters:
            words = sentence.split()
            word_piece = ""

            for word in words:
                candidate = f"{word_piece} {word}".strip()

                if word_piece and len(candidate) > max_characters:
                    if current_piece:
                        pieces.append(current_piece)
                        current_piece = ""

                    pieces.append(word_piece)
                    word_piece = word
                else:
                    word_piece = candidate

            if word_piece:
                if current_piece:
                    pieces.append(current_piece)
                    current_piece = ""

                pieces.append(word_piece)

            continue

        candidate = f"{current_piece} {sentence}".strip()

        if current_piece and len(candidate) > max_characters:
            pieces.append(current_piece)
            current_piece = sentence
        else:
            current_piece = candidate

    if current_piece:
        pieces.append(current_piece)

    return pieces


def split_paragraphs(
    paragraphs: list[str],
) -> list[list[str]]:
    """
    Divide a section into chunks while keeping paragraph boundaries.

    One paragraph is repeated between neighbouring chunks to preserve
    limited contextual continuity.
    """

    expanded_paragraphs: list[str] = []

    for paragraph in paragraphs:
        expanded_paragraphs.extend(
            split_long_paragraph(
                paragraph,
                MAX_CHARACTERS,
            )
        )

    groups: list[list[str]] = []
    current_group: list[str] = []
    current_length = 0

    for paragraph in expanded_paragraphs:
        separator_length = 2 if current_group else 0
        extra_length = len(paragraph) + separator_length

        if (
            current_group
            and current_length + extra_length > MAX_CHARACTERS
        ):
            groups.append(current_group)

            if OVERLAP_PARAGRAPHS:
                current_group = current_group[
                    -OVERLAP_PARAGRAPHS:
                ]
            else:
                current_group = []

            current_length = sum(
                len(item)
                for item in current_group
            )

            if len(current_group) > 1:
                current_length += 2 * (
                    len(current_group) - 1
                )

        current_group.append(paragraph)

        current_length += len(paragraph)

        if len(current_group) > 1:
            current_length += 2

    if current_group:
        groups.append(current_group)

    return groups


def load_source_manifest() -> dict[str, dict[str, Any]]:
    """
    Load provenance metadata created by the document loader.

    This lets every chunk retain the original source filename and hash.
    """

    if not DOCUMENT_MANIFEST.exists():
        return {}

    manifest_items = json.loads(
        DOCUMENT_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    return {
        item.get("output_file", ""): item
        for item in manifest_items
        if item.get("status") == "processed"
    }


def process_document(
    file_path: Path,
    source_metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    """Turn one cleaned strategy document into structured chunks."""

    raw_text = file_path.read_text(
        encoding="utf-8"
    )

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(
            r"\n\s*\n",
            raw_text,
        )
        if paragraph.strip()
    ]

    if not paragraphs:
        return []

    collection_title = strip_heading_marks(
        paragraphs[0]
    )

    current_theme: str | None = None
    current_section_title = "Document introduction"
    current_strategy_code: str | None = None
    current_strategy_title: str | None = None

    current_paragraphs: list[str] = []
    chunk_records: list[dict[str, Any]] = []

    section_number = 0

    def save_current_section() -> None:
        """Create chunks from the current section."""

        nonlocal current_paragraphs
        nonlocal section_number

        if not current_paragraphs:
            return

        section_number += 1

        paragraph_groups = split_paragraphs(
            current_paragraphs
        )

        for chunk_part, paragraph_group in enumerate(
            paragraph_groups,
            start=1,
        ):
            body_text = "\n\n".join(
                paragraph_group
            ).strip()

            section_type = (
                "strategy"
                if current_strategy_code
                else "context"
            )

            identifier = (
                current_strategy_code
                or slugify(current_section_title)[:30]
                or f"context_{section_number}"
            )

            chunk_id = (
                f"{slugify(file_path.stem)}"
                f"__{slugify(identifier)}"
                f"__{section_number:03d}"
                f"_{chunk_part:02d}"
            )

            metadata_text = [collection_title]

            if current_theme:
                metadata_text.append(current_theme)

            if (
                current_strategy_code
                and current_strategy_title
            ):
                metadata_text.append(
                    f"Strategy {current_strategy_code}: "
                    f"{current_strategy_title}"
                )
            elif current_section_title:
                metadata_text.append(
                    current_section_title
                )

            search_text = "\n".join(
                metadata_text + [body_text]
            )

            chunk_records.append(
                {
                    "chunk_id": chunk_id,
                    "source_file": source_metadata.get(
                        "source_file",
                        file_path.name,
                    ),
                    "processed_file": file_path.name,
                    "collection_title": collection_title,
                    "theme": current_theme,
                    "strategy_code": current_strategy_code,
                    "strategy_title": current_strategy_title,
                    "section_type": section_type,
                    "section_title": current_section_title,
                    "chunk_part": chunk_part,
                    "text": body_text,
                    "search_text": search_text,
                    "character_count": len(body_text),
                    "word_count": len(body_text.split()),
                    "source_sha256": source_metadata.get(
                        "sha256"
                    ),
                }
            )

        current_paragraphs = []

    for paragraph in paragraphs[1:]:
        detected_theme = detect_theme(paragraph)
        detected_strategy = detect_strategy(paragraph)

        if detected_theme:
            save_current_section()

            current_theme = detected_theme
            current_section_title = detected_theme
            current_strategy_code = None
            current_strategy_title = None
            current_paragraphs = []

            continue

        if detected_strategy:
            save_current_section()

            (
                current_strategy_code,
                current_strategy_title,
            ) = detected_strategy

            current_section_title = (
                f"Strategy {current_strategy_code}: "
                f"{current_strategy_title}"
            )

            current_paragraphs = []

            continue

        if looks_like_context_heading(paragraph):
            save_current_section()

            current_section_title = strip_heading_marks(
                paragraph
            )
            current_strategy_code = None
            current_strategy_title = None
            current_paragraphs = []

            continue

        current_paragraphs.append(
            strip_heading_marks(paragraph)
        )

    save_current_section()

    return chunk_records


def save_outputs(
    chunk_records: list[dict[str, Any]],
    chunks_per_document: dict[str, int],
) -> None:
    """Save chunks in JSONL, CSV and manifest formats."""

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_JSONL.open(
        "w",
        encoding="utf-8",
    ) as file:
        for record in chunk_records:
            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
                + "\n"
            )

    if chunk_records:
        with OUTPUT_CSV.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(
                    chunk_records[0].keys()
                ),
            )

            writer.writeheader()
            writer.writerows(chunk_records)

    summary = {
        "documents_processed": len(
            chunks_per_document
        ),
        "total_chunks": len(chunk_records),
        "strategy_chunks": sum(
            record["section_type"] == "strategy"
            for record in chunk_records
        ),
        "context_chunks": sum(
            record["section_type"] == "context"
            for record in chunk_records
        ),
        "max_characters_per_chunk": MAX_CHARACTERS,
        "overlap_paragraphs": OVERLAP_PARAGRAPHS,
        "chunks_per_document": chunks_per_document,
    }

    OUTPUT_MANIFEST.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main() -> None:
    """Chunk all processed strategy documents."""

    if not INPUT_DIR.exists():
        raise FileNotFoundError(
            f"Processed strategy folder not found: "
            f"{INPUT_DIR}. Run the document loader first."
        )

    source_manifest = load_source_manifest()

    processed_files = sorted(
        file_path
        for file_path in INPUT_DIR.glob("*.txt")
        if file_path.is_file()
    )

    if not processed_files:
        raise FileNotFoundError(
            f"No processed TXT files found in {INPUT_DIR}"
        )

    all_chunks: list[dict[str, Any]] = []
    chunks_per_document: dict[str, int] = {}

    print("\nHEY JOEY STRATEGY CHUNKER")
    print("=" * 60)

    for file_path in processed_files:
        source_metadata = source_manifest.get(
            file_path.name,
            {},
        )

        document_chunks = process_document(
            file_path,
            source_metadata,
        )

        all_chunks.extend(document_chunks)

        chunks_per_document[file_path.name] = len(
            document_chunks
        )

        strategy_chunk_count = sum(
            chunk["section_type"] == "strategy"
            for chunk in document_chunks
        )

        print(
            f"[OK] {file_path.name}: "
            f"{len(document_chunks)} chunks "
            f"({strategy_chunk_count} strategy chunks)"
        )

    save_outputs(
        all_chunks,
        chunks_per_document,
    )

    total_strategy_chunks = sum(
        chunk["section_type"] == "strategy"
        for chunk in all_chunks
    )

    total_context_chunks = sum(
        chunk["section_type"] == "context"
        for chunk in all_chunks
    )

    print("\nChunking summary")
    print("-" * 60)
    print(f"Documents processed: {len(processed_files)}")
    print(f"Total chunks: {len(all_chunks)}")
    print(f"Strategy chunks: {total_strategy_chunks}")
    print(f"Context chunks: {total_context_chunks}")
    print(f"JSONL output: {OUTPUT_JSONL}")
    print(f"CSV output: {OUTPUT_CSV}")
    print(f"Manifest: {OUTPUT_MANIFEST}")


if __name__ == "__main__":
    main()