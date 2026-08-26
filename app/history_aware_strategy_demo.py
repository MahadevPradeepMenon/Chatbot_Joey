from rag.history_aware_strategy_service import (
    HistoryAwareStrategyService,
)


# Keep retrieved passages short enough for a readable command-line demo.
def preview(text: str, maximum: int = 240) -> str:
    # Collapse repeated whitespace before applying the preview length limit.
    clean = " ".join(text.split())

    # Return short passages unchanged; longer passages are truncated below.
    if len(clean) <= maximum:
        return clean

    # Truncate at the final complete word rather than cutting a word in half.
    return clean[:maximum].rsplit(" ", maxsplit=1)[0] + "..."


# This CLI demonstrates how stored strategy history can influence the final
# ranking produced by the history-aware retrieval service.
def main() -> None:
    print("\nHEY JOEY HISTORY-AWARE STRATEGY DEMO")
    print("=" * 72)

    # Read one parent/carer strategy question directly from the command line.
    question = input(
        "Parent/carer strategy question: "
    ).strip()

    # Instantiate the service that combines context-aware retrieval with
    # previously stored strategy-history information.
    service = HistoryAwareStrategyService()
    # Request three displayed results from a larger candidate pool so the
    # history-aware ranking step has alternatives available to re-order.
    response = service.retrieve(
        question=question,
        top_k=3,
        candidate_pool=6,
    )

    print("\nSELECTED CONTEXT")
    print("=" * 72)
    # Show the historical/profile context selected for the current question.
    print(response.context.context_text)

    print("\nHISTORY-AWARE RESULTS")
    print("=" * 72)

    # Print each final evidence item together with its original retrieval rank
    # and the adjustment introduced by stored strategy history.
    for item in response.evidence:
        # Include the strategy code when one is available for easier tracing
        # back to the approved strategy source.
        title = (
            f"{item.strategy_code}: {item.strategy_title}"
            if item.strategy_code
            else item.strategy_title
        )

        print("\n" + "-" * 72)
        print(
            f"Rank {item.rank} "
            f"| Original rank: {item.original_rank}"
        )
        # The original hybrid score is shown separately from the later
        # history-adjusted personalised score.
        print(
            f"Original hybrid score: "
            f"{item.original_score:.6f}"
        )
        # A signed value makes it clear whether history promoted or reduced
        # this strategy relative to its original retrieval score.
        print(
            f"History adjustment: "
            f"{item.history_adjustment:+.6f}"
        )
        print(
            f"Personalised score: "
            f"{item.personalised_score:.6f}"
        )
        print(f"Strategy: {title}")
        print(f"Collection: {item.collection_title}")
        print(f"Source: {item.source_file}")
        # The history note explains the stored evidence behind the adjustment.
        print(f"History: {item.history_note}")
        print(f"Passage: {preview(item.passage)}")


# Run the demo only when this file is executed directly.
if __name__ == "__main__":
    main()
