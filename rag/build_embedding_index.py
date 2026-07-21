import hashlib
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CHUNKS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "strategy_chunks"
    / "strategy_chunks.jsonl"
)

INDEX_DIR = PROJECT_ROOT / "data" / "indexes"

EMBEDDINGS_FILE = INDEX_DIR / "strategy_embeddings.npy"
METADATA_FILE = INDEX_DIR / "strategy_index_metadata.jsonl"
MANIFEST_FILE = INDEX_DIR / "strategy_index_manifest.json"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEVICE = "cpu"
BATCH_SIZE = 32


def calculate_sha256(file_path: Path) -> str:
    """Calculate a reproducible hash for the input chunk file."""

    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for block in iter(lambda: file.read(65536), b""):
            sha256.update(block)

    return sha256.hexdigest()


def load_chunks() -> list[dict[str, Any]]:
    """Load and validate the strategy chunk records."""

    if not CHUNKS_FILE.exists():
        raise FileNotFoundError(
            f"Strategy chunk file not found: {CHUNKS_FILE}\n"
            "Run python -m rag.strategy_chunker first."
        )

    records: list[dict[str, Any]] = []

    with CHUNKS_FILE.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON on line {line_number}: {error}"
                ) from error

            chunk_id = str(record.get("chunk_id", "")).strip()
            search_text = str(record.get("search_text", "")).strip()

            if not chunk_id:
                raise ValueError(
                    f"Missing chunk_id on line {line_number}"
                )

            if not search_text:
                raise ValueError(
                    f"Missing search_text for chunk {chunk_id}"
                )

            records.append(record)

    if not records:
        raise ValueError(
            f"No chunk records were loaded from {CHUNKS_FILE}"
        )

    chunk_ids = [
        str(record["chunk_id"])
        for record in records
    ]

    duplicate_ids = {
        chunk_id
        for chunk_id in chunk_ids
        if chunk_ids.count(chunk_id) > 1
    }

    if duplicate_ids:
        preview = sorted(duplicate_ids)[:5]

        raise ValueError(
            f"Duplicate chunk IDs found: {preview}"
        )

    return records


def build_embeddings(
    records: list[dict[str, Any]],
) -> tuple[np.ndarray, SentenceTransformer]:
    """Generate locally normalised embeddings for all strategy chunks."""

    search_texts = [
        str(record["search_text"])
        for record in records
    ]

    print(f"Loading local embedding model: {MODEL_NAME}")
    print("The first run may download the model files.")
    print()

    model = SentenceTransformer(
        MODEL_NAME,
        device=DEVICE,
    )

    embeddings = model.encode(
        search_texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    embeddings = np.asarray(
        embeddings,
        dtype=np.float32,
    )

    return embeddings, model


def validate_embeddings(
    embeddings: np.ndarray,
    expected_count: int,
) -> None:
    """Validate embedding count, shape and normalisation."""

    if embeddings.ndim != 2:
        raise ValueError(
            f"Expected a two-dimensional embedding array, "
            f"but received shape {embeddings.shape}"
        )

    if embeddings.shape[0] != expected_count:
        raise ValueError(
            f"Embedding count mismatch: expected {expected_count}, "
            f"received {embeddings.shape[0]}"
        )

    if embeddings.shape[1] == 0:
        raise ValueError(
            "The embedding dimension cannot be zero."
        )

    if not np.isfinite(embeddings).all():
        raise ValueError(
            "The embeddings contain NaN or infinite values."
        )

    vector_norms = np.linalg.norm(
        embeddings,
        axis=1,
    )

    if not np.allclose(
        vector_norms,
        1.0,
        atol=1e-4,
    ):
        raise ValueError(
            "The embeddings were not correctly normalised."
        )


def save_metadata(
    records: list[dict[str, Any]],
) -> None:
    """
    Save metadata in exactly the same order as the embedding rows.

    embedding_position identifies the corresponding row in the
    strategy_embeddings.npy array.
    """

    with METADATA_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        for position, record in enumerate(records):
            metadata_record = {
                "embedding_position": position,
                **record,
            }

            file.write(
                json.dumps(
                    metadata_record,
                    ensure_ascii=False,
                )
                + "\n"
            )


def save_manifest(
    records: list[dict[str, Any]],
    embeddings: np.ndarray,
    model: SentenceTransformer,
) -> None:
    """Save reproducibility and index-validation information."""

    model_dimension = (
        model.get_sentence_embedding_dimension()
    )

    manifest = {
        "index_name": "hey_joey_strategy_semantic_index",
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "model_name": MODEL_NAME,
        "device": DEVICE,
        "sentence_transformers_version": version(
            "sentence-transformers"
        ),
        "numpy_version": np.__version__,
        "source_chunks_file": str(
            CHUNKS_FILE.relative_to(PROJECT_ROOT)
        ),
        "source_chunks_sha256": calculate_sha256(
            CHUNKS_FILE
        ),
        "chunk_count": len(records),
        "embedding_count": int(
            embeddings.shape[0]
        ),
        "embedding_dimension": int(
            embeddings.shape[1]
        ),
        "model_reported_dimension": model_dimension,
        "embedding_dtype": str(
            embeddings.dtype
        ),
        "normalised_embeddings": True,
        "similarity_method": (
            "cosine similarity using dot product "
            "between unit-normalised vectors"
        ),
        "embeddings_file": EMBEDDINGS_FILE.name,
        "metadata_file": METADATA_FILE.name,
    }

    MANIFEST_FILE.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main() -> None:
    """Build the local Hey Joey strategy embedding index."""

    INDEX_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("\nHEY JOEY LOCAL EMBEDDING INDEX BUILDER")
    print("=" * 60)

    records = load_chunks()

    print(f"Chunks loaded: {len(records)}")

    embeddings, model = build_embeddings(
        records
    )

    validate_embeddings(
        embeddings,
        expected_count=len(records),
    )

    # The array contains only numeric values, so pickle is disabled.
    np.save(
        EMBEDDINGS_FILE,
        embeddings,
        allow_pickle=False,
    )

    save_metadata(records)
    save_manifest(
        records,
        embeddings,
        model,
    )

    print("\nEmbedding index summary")
    print("-" * 60)
    print(f"Chunks loaded: {len(records)}")
    print(
        f"Embeddings created: "
        f"{embeddings.shape[0]}"
    )
    print(
        f"Embedding dimensions: "
        f"{embeddings.shape[1]}"
    )
    print(
        f"Embedding data type: "
        f"{embeddings.dtype}"
    )
    print("Normalised embeddings: Yes")
    print(f"Embeddings: {EMBEDDINGS_FILE}")
    print(f"Metadata: {METADATA_FILE}")
    print(f"Manifest: {MANIFEST_FILE}")
    print("\nLocal semantic index created successfully.")


if __name__ == "__main__":
    main()