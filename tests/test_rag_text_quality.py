from gateway.rag.text_quality import clean_document_text, score_text_quality


def test_clean_document_text_removes_common_pdf_artifacts():
    raw_text = """
    Climate strategy and governance oversight improved across the reporting year.
    12 0 obj << /Type/Page /Resources 5 0 R >> endobj
    https://example.com/report.pdf
    Worker safety training hours increased and injury rates declined.
    """

    cleaned = clean_document_text(raw_text, min_line_score=0.18)

    assert "Climate strategy and governance oversight" in cleaned
    assert "Worker safety training hours increased" in cleaned
    assert "endobj" not in cleaned.lower()
    assert "/Type/Page" not in cleaned
    assert "https://example.com/report.pdf" not in cleaned


def test_score_text_quality_prefers_natural_language_over_pdf_noise():
    grounded_text = (
        "The company reduced Scope 1 emissions by 12 percent and expanded board oversight "
        "of climate and cyber risk across all operating entities."
    )
    noisy_text = "12 0 obj << /Type/Page /Parent 3 0 R /Resources 5 0 R >> endobj"

    assert score_text_quality(grounded_text) > score_text_quality(noisy_text)
    assert score_text_quality(grounded_text) >= 0.45
    assert score_text_quality(noisy_text) <= 0.05
