import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer


# Resolve index paths relative to the repository so retrieval works consistently
# regardless of the current working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

INDEX_DIR = PROJECT_ROOT / "data" / "indexes"

EMBEDDINGS_FILE = INDEX_DIR / "strategy_embeddings.npy"
METADATA_FILE = INDEX_DIR / "strategy_index_metadata.jsonl"
MANIFEST_FILE = INDEX_DIR / "strategy_index_manifest.json"

# Keep default retrieval size and local CPU execution explicit for predictable use.
DEFAULT_TOP_K = 5
DEFAULT_DEVICE = "cpu"


@dataclass(frozen=True)
class SemanticSearchResult:
    """One strategy passage returned by semantic retrieval."""

    rank: int
    score: float
    chunk_id: str
    source_file: str
    collection_title: str
    theme: str | None
    strategy_code: str | None
    strategy_title: str | None
    section_type: str
    section_title: str
    chunk_part: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        """Convert the search result into a serialisable dictionary."""

        return asdict(self)


class SemanticStrategyRetriever:
    """
    Search the local Hey Joey strategy index by semantic meaning.

    The retriever does not call a paid API. It loads the embedding
    model and strategy index locally.
    """

    def __init__(
        self,
        embeddings_file: Path = EMBEDDINGS_FILE,
        metadata_file: Path = METADATA_FILE,
        manifest_file: Path = MANIFEST_FILE,
        device: str = DEFAULT_DEVICE,
    ) -> None:
        self.embeddings_file = embeddings_file
        self.metadata_file = metadata_file
        self.manifest_file = manifest_file
        self.device = device

        # Validate that all index artifacts exist before attempting to load or query them.
        self._check_required_files()

        # Load manifest, embeddings and metadata together so their alignment can
        # be checked before the model is used.
        self.manifest = self._load_manifest()
        self.embeddings = self._load_embeddings()
        self.metadata = self._load_metadata()

        self._validate_index()

        # Use the exact model recorded when the index was built to keep query and
        # corpus embeddings in the same vector space.
        model_name = str(self.manifest["model_name"])

        print(f"Loading local semantic model: {model_name}")

        self.model = SentenceTransformer(
            model_name,
            device=self.device,
        )

    def _check_required_files(self) -> None:
        """Confirm that the index files created in Step 13 exist."""

        # The semantic index is only usable when embeddings, metadata and manifest
        # are all present as a matching artifact set.
        required_files = [
            self.embeddings_file,
            self.metadata_file,
            self.manifest_file,
        ]

        missing_files = [
            file_path
            for file_path in required_files
            if not file_path.exists()
        ]

        if missing_files:
            missing_text = "\n".join(
                f"- {file_path}"
                for file_path in missing_files
            )

            raise FileNotFoundError(
                "The semantic index is incomplete.\n"
                f"Missing files:\n{missing_text}\n\n"
                "Run python -m rag.build_embedding_index first."
            )

    def _load_manifest(self) -> dict[str, Any]:
        """Load the index manifest."""

        # Parse the manifest as UTF-8 JSON and surface malformed content clearly.
        try:
            return json.loads(
                self.manifest_file.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid index manifest: {error}"
            ) from error

    def _load_embeddings(self) -> np.ndarray:
        """Load the saved embedding matrix."""

        # Load the numeric embedding matrix with pickle disabled for a narrow,
        # predictable data-loading path.
        embeddings = np.load(
            self.embeddings_file,
            allow_pickle=False,
        )

        return np.asarray(
            embeddings,
            dtype=np.float32,
        )

    def _load_metadata(self) -> list[dict[str, Any]]:
        """Load metadata in embedding-position order."""

        records: list[dict[str, Any]] = []

        # Read metadata line-by-line so malformed JSON can be reported with its
        # exact line number.
        with self.metadata_file.open(
            "r",
            encoding="utf-8",
        ) as file:
            for line_number, line in enumerate(
                file,
                start=1,
            ):
                line = line.strip()

                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        "Invalid metadata JSON on "
                        f"line {line_number}: {error}"
                    ) from error

                records.append(record)

        # Restore embedding-position order so metadata row N corresponds to
        # embedding row N.
        records.sort(
            key=lambda record: int(
                record.get(
                    "embedding_position",
                    -1,
                )
            )
        )

        return records

    def _validate_index(self) -> None:
        """Validate alignment between embeddings and metadata."""

        # Validate dimensionality, row alignment, manifest counts and numeric
        # integrity before allowing any search requests.
        if self.embeddings.ndim != 2:
            raise ValueError(
                "Expected a two-dimensional embedding array, "
                f"but received {self.embeddings.shape}."
            )

        embedding_count = int(
            self.embeddings.shape[0]
        )

        metadata_count = len(self.metadata)

        if embedding_count != metadata_count:
            raise ValueError(
                "Index alignment error: "
                f"{embedding_count} embeddings but "
                f"{metadata_count} metadata records."
            )

        # Require contiguous zero-based metadata positions to prevent row/chunk
        # mismatches during retrieval.
        expected_positions = list(
            range(metadata_count)
        )

        actual_positions = [
            int(
                record.get(
                    "embedding_position",
                    -1,
                )
            )
            for record in self.metadata
        ]

        if actual_positions != expected_positions:
            raise ValueError(
                "Metadata embedding positions are missing, "
                "duplicated or out of order."
            )

        # Cross-check manifest counts and dimensions against the loaded array.
        manifest_chunk_count = int(
            self.manifest.get(
                "chunk_count",
                -1,
            )
        )

        if manifest_chunk_count != embedding_count:
            raise ValueError(
                "Manifest count does not match the index: "
                f"manifest={manifest_chunk_count}, "
                f"embeddings={embedding_count}."
            )

        manifest_dimension = int(
            self.manifest.get(
                "embedding_dimension",
                -1,
            )
        )

        actual_dimension = int(
            self.embeddings.shape[1]
        )

        if manifest_dimension != actual_dimension:
            raise ValueError(
                "Manifest embedding dimension does not match "
                f"the array: manifest={manifest_dimension}, "
                f"array={actual_dimension}."
            )

        if not np.isfinite(
            self.embeddings
        ).all():
            raise ValueError(
                "The embedding index contains invalid values."
            )

    def _embed_query(
        self,
        query: str,
    ) -> np.ndarray:
        """Convert one parent query into a normalised local embedding."""

        # Collapse repeated whitespace before embedding so semantically identical
        # queries are treated consistently.
        clean_query = " ".join(
            query.split()
        ).strip()

        if not clean_query:
            raise ValueError(
                "The search query cannot be empty."
            )

        # Normalise the query vector just like the stored corpus embeddings so
        # cosine similarity can be computed as a dot product.
        query_embedding = self.model.encode(
            [clean_query],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]

        query_embedding = np.asarray(
            query_embedding,
            dtype=np.float32,
        )

        # Guard against model/index incompatibility by checking vector dimension.
        expected_dimension = int(
            self.embeddings.shape[1]
        )

        if query_embedding.shape != (
            expected_dimension,
        ):
            raise ValueError(
                "Query embedding dimension does not match "
                f"the index. Expected {expected_dimension}, "
                f"received {query_embedding.shape}."
            )

        return query_embedding

    @staticmethod
    def _strategy_identity(
        record: dict[str, Any],
    ) -> tuple[str, str, str]:
        """
        Return a stable identity used to prevent repeated chunks
        from the same strategy dominating the results.
        """

        # Source file, strategy code and strategy title together provide a stable
        # identity for strategy-level deduplication.
        return (
            str(record.get("source_file", "")),
            str(record.get("strategy_code", "")),
            str(record.get("strategy_title", "")),
        )

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        strategy_only: bool = True,
        minimum_score: float | None = None,
        deduplicate_strategies: bool = True,
    ) -> list[SemanticSearchResult]:
        """
        Retrieve the most semantically similar strategy passages.

        Similarity scores are cosine-similarity values because both
        the index and query embeddings are unit-normalised.
        """

        # Validate retrieval parameters before embedding and ranking the query.
        if top_k < 1:
            raise ValueError(
                "top_k must be at least 1."
            )

        query_embedding = self._embed_query(
            query
        )

        # Both sides are unit-normalised, so matrix-vector dot products are
        # cosine-similarity scores.
        similarity_scores = (
            self.embeddings
            @ query_embedding
        )

        # Sort embedding positions by descending semantic similarity.
        ranked_positions = np.argsort(
            similarity_scores
        )[::-1]

        results: list[SemanticSearchResult] = []
        seen_strategies: set[
            tuple[str, str, str]
        ] = set()

        for position in ranked_positions:
            position_number = int(position)
            record = self.metadata[
                position_number
            ]

            section_type = str(
                record.get(
                    "section_type",
                    "context",
                )
            )

            # Exclude contextual chunks when the caller requests strategy-only retrieval.
            if (
                strategy_only
                and section_type != "strategy"
            ):
                continue

            score = float(
                similarity_scores[
                    position_number
                ]
            )

            # Optional score filtering can remove weak semantic matches before display.
            if (
                minimum_score is not None
                and score < minimum_score
            ):
                continue

            # Keep only the highest-ranked chunk from each strategy when deduplication
            # is enabled.
            if deduplicate_strategies:
                strategy_identity = (
                    self._strategy_identity(
                        record
                    )
                )

                if strategy_identity in seen_strategies:
                    continue

                seen_strategies.add(
                    strategy_identity
                )

            # Convert the aligned metadata row into a typed result using the final
            # post-filter rank.
            result = SemanticSearchResult(
                rank=len(results) + 1,
                score=score,
                chunk_id=str(
                    record.get(
                        "chunk_id",
                        "",
                    )
                ),
                source_file=str(
                    record.get(
                        "source_file",
                        "",
                    )
                ),
                collection_title=str(
                    record.get(
                        "collection_title",
                        "",
                    )
                ),
                theme=record.get("theme"),
                strategy_code=record.get(
                    "strategy_code"
                ),
                strategy_title=record.get(
                    "strategy_title"
                ),
                section_type=section_type,
                section_title=str(
                    record.get(
                        "section_title",
                        "",
                    )
                ),
                chunk_part=int(
                    record.get(
                        "chunk_part",
                        1,
                    )
                ),
                text=str(
                    record.get(
                        "text",
                        "",
                    )
                ),
            )

            results.append(result)

            # Stop once the requested number of final results has been collected.
            if len(results) >= top_k:
                break

        return results


def shorten_text(
    text: str,
    maximum_characters: int = 600,
) -> str:
    """Create a readable terminal preview of a retrieved passage."""

    # Collapse whitespace only for terminal display; retrieval content is unchanged.
    clean_text = " ".join(
        text.split()
    )

    if len(clean_text) <= maximum_characters:
        return clean_text

    shortened = clean_text[
        :maximum_characters
    ].rsplit(
        " ",
        maxsplit=1,
    )[0]

    return f"{shortened}..."


def print_results(
    query: str,
    results: list[SemanticSearchResult],
    show_full_text: bool = False,
) -> None:
    """Display retrieved strategies in a readable terminal format."""

    print("\nHEY JOEY SEMANTIC STRATEGY RETRIEVAL")
    print("=" * 70)
    print(f"Query: {query}")
    print(f"Results returned: {len(results)}")

    if not results:
        print(
            "\nNo strategy passages met the search criteria."
        )
        return

    for result in results:
        strategy_label = (
            f"{result.strategy_code}: "
            f"{result.strategy_title}"
            if result.strategy_code
            and result.strategy_title
            else result.section_title
        )

        passage = (
            result.text
            if show_full_text
            else shorten_text(result.text)
        )

        print("\n" + "-" * 70)
        print(
            f"Rank {result.rank} "
            f"| Similarity: {result.score:.4f}"
        )
        print(f"Strategy: {strategy_label}")
        print(
            f"Collection: "
            f"{result.collection_title}"
        )
        print(f"Source: {result.source_file}")

        if result.theme:
            print(f"Theme: {result.theme}")

        print(f"Chunk ID: {result.chunk_id}")
        print(f"\nPassage:\n{passage}")


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""

    # The CLI exposes retrieval controls for manual testing without changing
    # the underlying retriever defaults.
    parser = argparse.ArgumentParser(
        description=(
            "Search the local Hey Joey strategy "
            "index using semantic similarity."
        )
    )

    parser.add_argument(
        "query",
        help="Parent note or support query to search for.",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help="Number of results to return. Default: 5.",
    )

    parser.add_argument(
        "--include-context",
        action="store_true",
        help=(
            "Include contextual sections as well as "
            "individual strategy sections."
        ),
    )

    parser.add_argument(
        "--minimum-score",
        type=float,
        default=None,
        help=(
            "Optional minimum cosine-similarity score."
        ),
    )

    parser.add_argument(
        "--allow-duplicate-strategies",
        action="store_true",
        help=(
            "Allow multiple chunks from the same strategy."
        ),
    )

    parser.add_argument(
        "--full-text",
        action="store_true",
        help=(
            "Display the complete retrieved passage."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """Run semantic retrieval from the terminal."""

    # Parse CLI options, build the local retriever once, then execute one query.
    arguments = parse_arguments()

    retriever = SemanticStrategyRetriever()

    results = retriever.search(
        query=arguments.query,
        top_k=arguments.top_k,
        strategy_only=not arguments.include_context,
        minimum_score=arguments.minimum_score,
        deduplicate_strategies=(
            not arguments.allow_duplicate_strategies
        ),
    )

    print_results(
        query=arguments.query,
        results=results,
        show_full_text=arguments.full_text,
    )


# Run terminal retrieval only when this module is executed directly.
if __name__ == "__main__":
    main()