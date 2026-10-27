from types import SimpleNamespace

from src.rag_pipeline import (
    RAGPipeline,
    _deterministic_refund_date_fallback,
    _deterministic_return_window_fallback,
    _is_return_window_question,
)
from scripts.evaluate_questions import RetryingChatClient, contains_any, score_answer


REF2 = """## [REF-2] How long refunds take after initiation
| Payment method | Time to reach you |
| --- | --- |
| UPI | 1 to 3 business days |
| Credit or debit card | 5 to 7 business days |
| Net banking | 3 to 5 business days |
| ZentroMart Wallet | Instant, within 2 hours |
| Bank transfer (NEFT) for cash-on-delivery orders | 5 to 7 business days |
| ZentroMart Wallet for cash-on-delivery orders | Instant, within 2 hours |
"""

KB003 = """## [KB-00.3] Business days
A business day is Monday to Saturday, excluding the warehouse holidays below.
| Date | Holiday |
| --- | --- |
| 2026-08-15 | Independence Day |
| 2026-10-02 | Gandhi Jayanti |
| 2026-10-19 | Warehouse closure (festival) |
| 2026-11-09 | Warehouse closure (festival |
"""

KB002 = """## [KB-00.2] Today's date
All records in this dataset are frozen on 20 October 2026. Treat this date as today.
"""

RET2 = """## [RET-2] Return windows by category
| Category | Return window | Catalog code |
| --- | --- | --- |
| Electronics and accessories | 7 days | `electronics` |
| Clothing, footwear and bags | 15 days | `fashion` |
| Home, kitchen and furniture | 10 days | `home_kitchen` |
| Beauty and personal care (unopened, seal intact) | 7 days | `beauty_sealed` |
| Books and stationery | 10 days | `books_media` |
| Grocery, fresh and perishables | Not returnable | `grocery` |
| Innerwear, lingerie and swimwear | Not returnable | `innerwear` |
| Gift cards and digital codes | Not returnable | `digital` |
"""

RET3 = """## [RET-3] Change to electronics returns
From 1 August 2026, electronics return window is 7 days. Electronics delivered before 1 August 2026 keep the earlier 10-day window.
"""
RET8 = """## [RET-8] Festive sale returns
Clothing, footwear and bags from orders placed between 01 October and 15 October 2026 can be returned within 30 days of delivery.
"""
PRODUCT = {
    "source": "products.csv:FSH-0026",
    "section_id": "FSH-0026",
    "status": "current",
    "doc_type": "catalog",
    "product_title": "Rangoli Cotton Straight Kurta, White",
    "text": "Product catalog record. sku: FSH-0026. title: Rangoli Cotton Straight Kurta, White. return category: fashion.",
    "score": 1.2,
}


def _chunk(source, section, text, status="current", **extra):
    return {
        "source": source, "section_id": section, "status": status,
        "text": text, "score": extra.pop("score", 0.5), **extra
    }


def _chunks():
    return [
        _chunk("pol_returns_v4.md", "RET-2", RET2),
        PRODUCT,
        _chunk("00_about_this_knowledge_base.md", "KB-00.2", KB002),
        _chunk("00_about_this_knowledge_base.md", "KB-00.3", KB003),
        _chunk("pol_refunds.md", "REF-2", REF2),
        _chunk("pol_returns_v4.md", "RET-3", RET3),
        _chunk("pol_returns_v4.md", "RET-8", RET8),
    ]


def test_card_refund_date_uses_holiday_aware_business_days():
    answer = _deterministic_refund_date_fallback(
        "My refund to credit card was started on 17 October 2026. By which date should I have it?",
        _chunks(),
    )
    assert "2026-10-24" in answer
    assert "2026-10-27" in answer


def test_upi_refund_date_is_calculated_from_ref2_and_kb003():
    answer = _deterministic_refund_date_fallback(
        "UPI wala refund 12 October 2026 ko shuru hua, kab tak aa jaana chahiye?",
        _chunks(),
    )
    assert "2026-10-15" in answer
    assert "REF-2" in answer


def test_net_banking_refund_date_handles_sunday_and_holiday():
    answer = _deterministic_refund_date_fallback(
        "My refund to net banking was started on 17 October 2026. By which date should I have it?",
        _chunks(),
    )
    assert "2026-10-22" in answer
    assert "2026-10-24" in answer


def test_refund_date_does_not_calculate_without_holiday_evidence():
    chunks = [c for c in _chunks() if c["section_id"] != "KB-00.3"]
    answer = _deterministic_refund_date_fallback(
        "My refund to credit card was started on 17 October 2026. By which date should I have it?",
        chunks,
    )
    assert answer == ""


def test_wallet_refund_does_not_invent_a_date_without_initiation_time():
    answer = _deterministic_refund_date_fallback(
        "My ZentroMart Wallet refund was started on 17 October 2026. By which date should I have it?",
        _chunks(),
    )
    assert answer == ""


def test_return_window_fallback_answers_standard_rule_and_conditional_exception():
    answer = _deterministic_return_window_fallback(
        "How long do I get to send back the Rangoli Cotton Straight Kurta?", _chunks()
    )
    assert "15 calendar days" in answer
    assert "2026-10-01 through 2026-10-15" in answer
    assert "order date" in answer


def test_return_window_fallback_preserves_hindi_language():
    answer = _deterministic_return_window_fallback(
        "मुझे Pagecraft A5 Ruled Notebook (Pack of 4) लौटाने के लिए कितने दिन मिलेंगे?",
        [
            c for c in _chunks()
            if c["section_id"] in {"RET-2", "FSH-0026"}
        ] + [
            _chunk("products.csv:BKS-0056", "BKS-0056",
                   "Product catalog record. title: Pagecraft A5 Ruled Notebook (Pack of 4). return category: books_media.",
                   product_title="Pagecraft A5 Ruled Notebook (Pack of 4)")
        ],
    )
    assert "10 calendar days" in answer
    assert "डिलीवरी" in answer


def test_number_word_counts_for_numeric_benchmark_requirement():
    assert contains_any("The courier will try to deliver up to three times.", "3")
    assert not contains_any("The order date is 2026-10-27.", "10")


def test_handoff_offer_does_not_turn_a_correct_answer_into_abstention():
    row = {
        "answerable": "True",
        "must_include": "unopened / seal / sealed",
        "must_not_include": "",
    }
    answer = (
        "Beauty products can only be returned if unopened with the seal intact. "
        "Since it was opened, it is not eligible for return. I can connect you with a human colleague."
    )
    scored = score_answer(answer, row)
    assert scored["include_requirements_met"] is True
    assert scored["abstained"] is False
    assert scored["correct"] is True


def test_unanswerable_question_still_requires_uncertainty_or_handoff():
    row = {
        "answerable": "False",
        "must_include": "don't have / no information / connect",
        "must_not_include": "",
    }
    scored = score_answer(
        "I don't have enough information to confirm that. I can connect you with support.",
        row,
    )
    assert scored["abstained"] is True
    assert scored["decision_ok"] is True




def test_festive_sale_order_date_without_year_uses_frozen_reference_date():
    answer = _deterministic_return_window_fallback(
        "I bought the Rangoli Cotton Straight Kurta in the sale on 5 October. How long can I return it?",
        _chunks(),
    )
    assert "30 calendar days" in answer
    assert "2026-10-05" in answer
    assert "RET-8" in answer


def test_fashion_order_outside_ret8_period_uses_standard_window():
    answer = _deterministic_return_window_fallback(
        "I bought the Rangoli Cotton Straight Kurta on 20 October. How long can I return it?",
        _chunks(),
    )
    assert "15 calendar days" in answer
    assert "2026-10-20" in answer
    assert "order date is unknown" not in answer.casefold()



def test_rag_pipeline_overrides_wrong_refund_dates_from_current_evidence():
    class StaticRetriever:
        def search(self, query, top_k=5):
            return _chunks()

    class FixedLLM:
        def complete(self, **kwargs):
            return SimpleNamespace(
                text="It should arrive between 2026-10-22 and 2026-10-25.",
                usage=None,
            )

    pipeline = RAGPipeline(StaticRetriever(), FixedLLM())
    answer, sources, _ = pipeline.answer(
        "My refund to credit card was started on 17 October 2026. By which date should I have it?",
        top_k=5,
    )
    assert "2026-10-27" in answer
    assert "2026-10-24" in answer
    assert "KB-00.3" in {source.get("section_id") for source in sources}


def test_rag_pipeline_resolves_return_window_after_llm_abstains():
    class StaticRetriever:
        def search(self, query, top_k=5):
            return _chunks()

    class FixedLLM:
        def complete(self, **kwargs):
            return SimpleNamespace(
                text="I don't have enough information to determine the exact return window. "
                     "I can connect you with a human colleague.",
                usage=None,
            )

    pipeline = RAGPipeline(StaticRetriever(), FixedLLM())
    answer, sources, _ = pipeline.answer(
        "I bought the Rangoli Cotton Straight Kurta in the sale on 5 October. How long can I return it?",
        top_k=5,
    )
    assert "30 calendar days" in answer
    assert "2026-10-05" in answer
    assert "RET-8" in {source.get("section_id") for source in sources}
    assert "outside the RET-8 exception period" not in answer



def test_rag_pipeline_overrides_wrong_general_window_when_ret8_date_is_explicit():
    class StaticRetriever:
        def search(self, query, top_k=5):
            return _chunks()

    class FixedLLM:
        def complete(self, **kwargs):
            return SimpleNamespace(
                text="The standard return window is 15 calendar days from delivery.",
                usage=None,
            )

    pipeline = RAGPipeline(StaticRetriever(), FixedLLM())
    answer, sources, _ = pipeline.answer(
        "I bought the Rangoli Cotton Straight Kurta in the sale on 5 October. How long can I return it?",
        top_k=5,
    )
    assert "30 calendar days" in answer
    assert "2026-10-05" in answer
    assert "outside the RET-8 exception period" not in answer


def test_retrying_client_retries_transient_rate_limit_failure():
    class FlakyClient:
        def __init__(self):
            self.calls = 0

        def complete(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("LLM request failed (RateLimitError)")
            return SimpleNamespace(text="ok", usage=None)

    client = FlakyClient()
    retrying = RetryingChatClient(client, retries=2, delay=0)
    assert retrying.complete(system="s", user="u").text == "ok"
    assert client.calls == 2


def test_retrying_client_does_not_retry_nontransient_error():
    class BrokenClient:
        def __init__(self):
            self.calls = 0

        def complete(self, **kwargs):
            self.calls += 1
            raise RuntimeError("Invalid request")

    client = BrokenClient()
    retrying = RetryingChatClient(client, retries=2, delay=0)
    try:
        retrying.complete(system="s", user="u")
        assert False, "Expected a non-transient error"
    except RuntimeError as exc:
        assert "Invalid request" in str(exc)
    assert client.calls == 1



def test_generic_return_eligibility_question_is_not_misclassified_as_window_question():
    assert _is_return_window_question("How many days do I have to return it?") is True
    assert _is_return_window_question("Can I still return it?") is False


def test_thanks_followup_does_not_repeat_prior_return_window_answer():
    class StaticRetriever:
        def search(self, query, top_k=5):
            return _chunks()

    class FixedLLM:
        def complete(self, **kwargs):
            return SimpleNamespace(text="You're welcome!", usage=None)

    pipeline = RAGPipeline(StaticRetriever(), FixedLLM())
    answer, _, _ = pipeline.answer(
        "Thanks",
        history=[{
            "role": "user",
            "content": (
                "I bought the Rangoli Cotton Straight Kurta in the sale on 5 October. "
                "How long can I return it?"
            ),
        }],
    )
    assert answer == "You're welcome!"
    assert "30 calendar days" not in answer
