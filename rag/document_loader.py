import hashlib

import json

import re

import zipfile

from pathlib import Path

from typing import Any

from docx import Document



# Resolve all input/output locations relative to the repository so preprocessing
# is reproducible regardless of the current working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

SOURCE_DIR = PROJECT_ROOT / "data" / "raw" / "strategies"

OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "strategies_text"

MANIFEST_FILE = OUTPUT_DIR / "strategy_document_manifest.json"



def calculate_sha256(file_path: Path) -> str:

    """Calculate a reproducible hash for a source document."""

    # Hash the original bytes in fixed-size blocks so source provenance can be
    # recorded without loading an entire document into memory.
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:

        for block in iter(lambda: file.read(65536), b""):

            sha256.update(block)

    return sha256.hexdigest()



def is_real_docx(file_path: Path) -> bool:

    """

    Determine whether a file is a genuine DOCX document.

    A DOCX file is a ZIP archive containing Word-specific files.

    This checks the actual contents rather than trusting the extension.

    """

    # A .docx extension alone is not trusted because some source files may carry
    # an incorrect extension.
    if not zipfile.is_zipfile(file_path):

        return False

    try:

        with zipfile.ZipFile(file_path, "r") as archive:

            # Genuine DOCX files must contain the core Open XML package entries.
            names = set(archive.namelist())

            return (

                "[Content_Types].xml" in names

                and "word/document.xml" in names

            )

    except zipfile.BadZipFile:

        return False



def extract_docx_text(file_path: Path) -> str:

    """

    Extract text from a genuine Word document.

    Heading markers are preserved so the later chunking stage can

    recognise collections, themes and individual strategies.

    """

    # python-docx is used only after the file has passed the DOCX structure check.
    document = Document(str(file_path))

    lines: list[str] = []

    for paragraph in document.paragraphs:

        text = paragraph.text.strip()

        if not text:

            continue

        style = paragraph.style

        style_name = (

            style.name.lower()

            if style is not None and style.name

            else ""

        )

        # Convert Word heading styles into lightweight Markdown-style markers
        # that the downstream chunker can recognise deterministically.
        if "heading 1" in style_name:

            lines.append(f"# {text}")

        elif "heading 2" in style_name:

            lines.append(f"## {text}")

        elif "heading 3" in style_name:

            lines.append(f"### {text}")

        else:

            lines.append(text)

    # This also supports future documents containing tables.
    # Table cells are flattened row-by-row so their text remains retrievable.

    for table in document.tables:

        for row in table.rows:

            cells = [

                cell.text.strip()

                for cell in row.cells

                if cell.text.strip()

            ]

            if cells:

                lines.append(" | ".join(cells))

    return "\n\n".join(lines)



def extract_plain_text(file_path: Path) -> str:

    """

    Read a plain-text file, including one carrying an incorrect

    extension such as the eating/mealtime document.

    """

    # Try a small deterministic encoding fallback list to accommodate legacy
    # plain-text sources without silently replacing undecodable characters.
    encodings = ["utf-8-sig", "utf-8", "utf-16", "cp1252"]

    for encoding in encodings:

        try:

            return file_path.read_text(encoding=encoding)

        except UnicodeDecodeError:

            continue

    raise UnicodeDecodeError(

        "unknown",

        b"",

        0,

        1,

        f"Could not decode {file_path.name}",

    )



def clean_text(text: str) -> str:

    """Normalise whitespace while preserving document structure."""

    # Normalise non-breaking spaces and line endings before collapsing internal
    # horizontal whitespace; blank-line paragraph structure is rebuilt below.
    text = text.replace("\u00a0", " ")

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    cleaned_lines: list[str] = []

    for line in text.splitlines():

        line = re.sub(r"[ \t]+", " ", line).strip()

        if line:

            cleaned_lines.append(line)

    return "\n\n".join(cleaned_lines)



def create_output_filename(source_file: Path) -> str:

    """Create a safe and consistent processed filename."""

    # Restrict processed filenames to lowercase ASCII letters, digits and
    # underscores for stable cross-platform output names.
    stem = source_file.stem.lower()

    stem = re.sub(r"[^a-z0-9]+", "_", stem)

    stem = stem.strip("_")

    return f"{stem}.txt"



def detect_and_extract(file_path: Path) -> tuple[str, str]:

    """

    Detect the real file format and return:

    (detected format, extracted text).

    """

    # Detect by file contents first; anything not recognised as DOCX is read as
    # plain text, including incorrectly named source files.
    if is_real_docx(file_path):

        return "docx", extract_docx_text(file_path)

    return "plain_text", extract_plain_text(file_path)



def process_document(file_path: Path) -> dict[str, Any]:

    """Process one strategy source document."""

    # Keep format detection, cleaning and output naming as separate deterministic
    # stages so each processed document can be traced in the manifest.
    detected_format, raw_text = detect_and_extract(file_path)

    cleaned_text = clean_text(raw_text)

    output_filename = create_output_filename(file_path)

    output_path = OUTPUT_DIR / output_filename

    # All processed corpus text is written as UTF-8 for consistent downstream
    # chunking and indexing.
    output_path.write_text(cleaned_text, encoding="utf-8")

    return {

        "source_file": file_path.name,

        "source_extension": file_path.suffix.lower(),

        "detected_format": detected_format,

        "output_file": output_filename,

        "character_count": len(cleaned_text),

        "paragraph_count": len(

            [line for line in cleaned_text.split("\n\n") if line.strip()]

        ),

        # Record a source hash so the manifest identifies the exact input bytes
        # used to produce this processed text file.
        "sha256": calculate_sha256(file_path),

        "status": "processed",

    }



def main() -> None:

    """Process all local Hey Joey strategy documents."""

    # Fail early when the expected local corpus directory is missing rather than
    # producing an empty manifest.
    if not SOURCE_DIR.exists():

        raise FileNotFoundError(

            f"Strategy source folder not found: {SOURCE_DIR}"

        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Sort the source paths to keep processing order and manifest output stable
    # across runs.
    supported_files = sorted(

        file_path

        for file_path in SOURCE_DIR.iterdir()

        if file_path.is_file()

        and file_path.suffix.lower() in {".docx", ".txt"}

    )

    if not supported_files:

        raise FileNotFoundError(

            f"No DOCX or TXT strategy files found in {SOURCE_DIR}"

        )

    manifest: list[dict[str, Any]] = []

    print("\nHEY JOEY STRATEGY DOCUMENT LOADER")

    print("=" * 60)

    # Process files independently so one malformed source is recorded as failed
    # without preventing the rest of the corpus from being prepared.
    for file_path in supported_files:

        try:

            result = process_document(file_path)

            manifest.append(result)

            print(

                f"[OK] {result['source_file']} "

                f"→ {result['detected_format']} "

                f"→ {result['output_file']}"

            )

        except Exception as error:

            manifest.append(

                {

                    "source_file": file_path.name,

                    "status": "failed",

                    "error": str(error),

                }

            )

            print(f"[FAILED] {file_path.name}: {error}")

    # Persist both successes and failures as a reproducibility/audit record of
    # the preprocessing run.
    MANIFEST_FILE.write_text(

        json.dumps(manifest, indent=2, ensure_ascii=False),

        encoding="utf-8",

    )

    # Summarise the manifest rather than maintaining separate mutable counters
    # during processing.
    successful = sum(

        item["status"] == "processed"

        for item in manifest

    )

    failed = sum(

        item["status"] == "failed"

        for item in manifest

    )

    print("\nProcessing summary")

    print("-" * 60)

    print(f"Source documents: {len(supported_files)}")

    print(f"Successfully processed: {successful}")

    print(f"Failed: {failed}")

    print(f"Manifest: {MANIFEST_FILE}")

    print(f"Processed text folder: {OUTPUT_DIR}")



# Run corpus preprocessing only when this module is executed directly.
if __name__ == "__main__":

    main()
