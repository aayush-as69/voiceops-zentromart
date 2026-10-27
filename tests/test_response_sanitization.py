from src.rag_pipeline import _sanitize_generated_answer


def test_removes_repeated_assistant_introductions():
    answer = (
        "Hello, I’m ZentroMart’s AI support assistant. "
        "I’m an AI assistant from ZentroMart. "
        "For a damaged item, the return policy applies."
    )

    result = _sanitize_generated_answer(answer, [], "What is the policy?")

    assert result == "For a damaged item, the return policy applies."


def test_corrects_observed_refund_durations_with_ref2_evidence():
    chunks = [{
        "source": "pol_refunds.md",
        "section_id": "REF-2",
    }]
    answer = (
        "Payment timelines are 13 business days for UPI and "
        "57 business days for cards."
    )

    result = _sanitize_generated_answer(
        answer, chunks, "What are the refund timelines?"
    )

    assert result == (
        "Payment timelines are 1–3 business days for UPI and "
        "5–7 business days for cards."
    )


def test_does_not_change_durations_without_ref2_evidence():
    chunks = [{
        "source": "pol_returns_v4.md",
        "section_id": "RET-7",
    }]
    answer = "The text says 13 business days for UPI."

    assert _sanitize_generated_answer(
        answer, chunks, "What are the refund timelines?"
    ) == answer


def test_preserves_identity_answer_when_user_asks_who_assistant_is():
    answer = "I'm an AI assistant from ZentroMart. I can help with orders."

    result = _sanitize_generated_answer(
        answer, [], "Who are you?"
    )

    assert result == answer
