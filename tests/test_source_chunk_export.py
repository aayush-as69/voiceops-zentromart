from src.rag_pipeline import RAGPipeline


def test_summarize_sources_includes_actual_retrieved_chunk_text():
    chunk = {
        "source": "pol_refunds.md",
        "section_id": "REF-2",
        "title": "Refunds policy",
        "doc_type": "policy",
        "effective_from": "2026-06-15",
        "score": 1.23,
        "text": "UPI refunds take 1 to 3 business days.",
    }

    result = RAGPipeline.summarize_sources([chunk])

    assert len(result) == 1
    assert result[0]["source"] == "pol_refunds.md"
    assert result[0]["section_id"] == "REF-2"
    assert result[0]["text"] == "UPI refunds take 1 to 3 business days."
    assert result[0]["score"] == 1.23
