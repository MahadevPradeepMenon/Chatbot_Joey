import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from rag.semantic_retriever import METADATA_FILE


# Use a deterministic lowercase lexical tokenizer that preserves internal apostrophes.
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")
DEFAULT_TOP_K = 5
# Fixed BM25 parameters keep lexical scoring reproducible across runs.
BM25_K1 = 1.5
BM25_B = 0.75


@dataclass(frozen=True)
class BM25SearchResult:
    """One strategy passage returned by local BM25 retrieval."""

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
        return asdict(self)


def tokenize(text: str) -> list[str]:
    """Convert text into lowercase lexical tokens."""

    return TOKEN_PATTERN.findall(text.lower())


# Build a stable strategy identity so multiple chunks from one strategy can be deduplicated.
def strategy_identity(
    record: dict[str, Any],
) -> tuple[str, str, str]:
    """Return a stable strategy identity for deduplication."""

    source_file = str(record.get("source_file", ""))
    strategy_code = str(record.get("strategy_code") or "")
    strategy_title = str(record.get("strategy_title") or "")

    # Prefer source + strategy metadata when available; otherwise fall back to chunk ID.
    if strategy_code or strategy_title:
        return source_file, strategy_code, strategy_title

    return source_file, "", str(record.get("chunk_id", ""))


class BM25StrategyRetriever:
    """Search the existing local strategy chunks with BM25."""

    def __init__(self) -> None:
        # Prepare corpus statistics once at initialisation so searches only need scoring.
        self.metadata = self._load_metadata()
        self.documents = [
            tokenize(self._build_document_text(record))
            for record in self.metadata
        ]
        # Cache per-document term frequencies and lengths required by BM25.
        self.term_frequencies = [
            Counter(document)
            for document in self.documents
        ]
        self.document_lengths = [
            len(document)
            for document in self.documents
        ]

        if not self.documents:
            raise ValueError("The strategy metadata is empty.")

        # BM25 length normalisation compares each chunk with the corpus average length.
        self.average_document_length = (
            sum(self.document_lengths) / len(self.document_lengths)
        )

        # Count each term once per document when building document frequencies for IDF.
        self.document_frequencies: Counter[str] = Counter()
        for document in self.documents:
            self.document_frequencies.update(set(document))

        self.document_count = len(self.documents)

    @staticmethod
    def _load_metadata() -> list[dict[str, Any]]:
        """Load metadata in embedding-position order."""

        # Reuse semantic-index metadata so lexical and semantic retrieval share one corpus.
        if not METADATA_FILE.exists():
            raise FileNotFoundError(
                f"Strategy metadata not found: {METADATA_FILE}. "
                "Run python -m rag.build_embedding_index first."
            )

        records: list[dict[str, Any]] = []

        # Read metadata line-by-line and report malformed JSON with its source line number.
        with METADATA_FILE.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                clean_line = line.strip()

                if not clean_line:
                    continue

                try:
                    records.append(json.loads(clean_line))
                except json.JSONDecodeError as error:
                    raise ValueError(
                        "Invalid metadata JSON on "
                        f"line {line_number}: {error}"
                    ) from error

        # Restore embedding-position order for alignment with the semantic index metadata.
        records.sort(
            key=lambda record: int(
                record.get("embedding_position", -1)
            )
        )

        return records

    @staticmethod
    def _build_document_text(record: dict[str, Any]) -> str:
        """
        Build lexical text.

        Repeating titles and collection metadata gives exact matches in
        those fields slightly more importance than ordinary passage text.
        """

        # Repeat selected metadata fields to give exact lexical matches extra weight.
        collection = str(record.get("collection_title", ""))
        theme = str(record.get("theme") or "")
        strategy_title = str(record.get("strategy_title") or "")
        section_title = str(record.get("section_title", ""))
        passage = str(record.get("text", ""))

        return " ".join(
            [
                collection,
                collection,
                theme,
                theme,
                strategy_title,
                strategy_title,
                strategy_title,
                section_title,
                section_title,
                passage,
            ]
        )

    def _idf(self, term: str) -> float:
        """Calculate BM25 inverse document frequency."""

        # Rarer corpus terms receive a larger inverse-document-frequency contribution.
        document_frequency = self.document_frequencies.get(term, 0)

        return math.log(
            1.0
            + (
                self.document_count
                - document_frequency
                + 0.5
            )
            / (
                document_frequency
                + 0.5
            )
        )

    def _score_document(
        self,
        query_terms: list[str],
        position: int,
    ) -> float:
        """Calculate the BM25 score for one strategy chunk."""

        frequencies = self.term_frequencies[position]
        document_length = self.document_lengths[position]
        score = 0.0

        # Score each distinct query term once using BM25 term frequency, IDF and length normalisation.
        for term in set(query_terms):
            term_frequency = frequencies.get(term, 0)

            if term_frequency == 0:
                continue

            # BM25_B controls how strongly document length adjusts the term contribution.
            length_normalisation = (
                1.0
                - BM25_B
                + BM25_B
                * (
                    document_length
                    / self.average_document_length
                )
            )

            denominator = (
                term_frequency
                + BM25_K1
                * length_normalisation
            )

            score += (
                self._idf(term)
                * term_frequency
                * (BM25_K1 + 1.0)
                / denominator
            )

        return score

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        strategy_only: bool = True,
        deduplicate_strategies: bool = True,
    ) -> list[BM25SearchResult]:
        """Return the highest-scoring lexical strategy passages."""

        # Validate retrieval parameters before scoring the corpus.
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        # Tokenise the query with the same lexical rules used for the corpus.
        query_terms = tokenize(query)

        if not query_terms:
            raise ValueError("The search query cannot be empty.")

        scored_positions: list[tuple[float, int]] = []

        # Score eligible chunks; strategy_only excludes contextual chunks when requested.
        for position, record in enumerate(self.metadata):
            section_type = str(
                record.get("section_type", "context")
            )

            if strategy_only and section_type != "strategy":
                continue

            score = self._score_document(
                query_terms=query_terms,
                position=position,
            )

            # Keep only chunks with a positive lexical match to the query.
            if score > 0.0:
                scored_positions.append((score, position))

        # Rank candidates by descending BM25 score before strategy-level deduplication.
        scored_positions.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        results: list[BM25SearchResult] = []
        seen_strategies: set[tuple[str, str, str]] = set()

        for score, position in scored_positions:
            record = self.metadata[position]

            # Keep only the highest-scoring chunk for each stable strategy identity.
            if deduplicate_strategies:
                identity = strategy_identity(record)

                if identity in seen_strategies:
                    continue

                seen_strategies.add(identity)

            # Build the typed result after filtering so ranks reflect the final result order.
            results.append(
                BM25SearchResult(
                    rank=len(results) + 1,
                    score=float(score),
                    chunk_id=str(record.get("chunk_id", "")),
                    source_file=str(record.get("source_file", "")),
                    collection_title=str(
                        record.get("collection_title", "")
                    ),
                    theme=record.get("theme"),
                    strategy_code=record.get("strategy_code"),
                    strategy_title=record.get("strategy_title"),
                    section_type=str(
                        record.get("section_type", "context")
                    ),
                    section_title=str(
                        record.get("section_title", "")
                    ),
                    chunk_part=int(record.get("chunk_part", 1)),
                    text=str(record.get("text", "")),
                )
            )

            # Stop once the requested number of final strategy results has been collected.
            if len(results) >= top_k:
                break

        return results


def main() -> None:
    """Run a small BM25 smoke test."""

    # Fixed sensory-related query used as a lightweight manual smoke test.
    query = (
        "child overwhelmed by loud classroom noise "
        "and covering their ears"
    )

    retriever = BM25StrategyRetriever()
    results = retriever.search(query=query, top_k=5)

    print("\nHEY JOEY BM25 RETRIEVAL")
    print("=" * 70)
    print(f"Query: {query}")

    for result in results:
        print("\n" + "-" * 70)
        print(f"Rank {result.rank} | BM25 score: {result.score:.4f}")
        print(
            f"Strategy: {result.strategy_code} - "
            f"{result.strategy_title}"
        )
        print(f"Collection: {result.collection_title}")
        print(f"Source: {result.source_file}")


# Run the smoke test only when this module is executed directly.
if __name__ == "__main__":
    main()
