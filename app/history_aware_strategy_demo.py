from rag.history_aware_strategy_service import (
    HistoryAwareStrategyService,
)


def preview(text: str, maximum: int = 240) -> str:
    clean = " ".join(text.split())

    if len(clean) <= maximum:
        return clean

    return clean[:maximum].rsplit(" ", maxsplit=1)[0] + "..."


def main() -> None:
    print("\nHEY JOEY HISTORY-AWARE STRATEGY DEMO")
    print("=" * 72)

    question = input(
        "Parent/carer strategy question: "
    ).strip()

    service = HistoryAwareStrategyService()
    response = service.retrieve(
        question=question,
        top_k=3,
        candidate_pool=6,
    )

    print("\nSELECTED CONTEXT")
    print("=" * 72)
    print(response.context.context_text)

    print("\nHISTORY-AWARE RESULTS")
    print("=" * 72)

    for item in response.evidence:
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
        print(
            f"Original hybrid score: "
            f"{item.original_score:.6f}"
        )
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
        print(f"History: {item.history_note}")
        print(f"Passage: {preview(item.passage)}")


if __name__ == "__main__":
    main()
