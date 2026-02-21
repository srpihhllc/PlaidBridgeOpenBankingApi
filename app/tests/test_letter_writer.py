# =============================================================================
# FILE: tests/test_letter_writer.py
# DESCRIPTION: Unit tests for letter_writer service functions.
# =============================================================================


from app.services import letter_writer


def test_letter_render_to_text_with_none():
    """render_letter_to_text(None) should return a placeholder string."""
    assert letter_writer.render_letter_to_text(None) == "[No letter content]"


def test_letter_render_to_text_with_string():
    """render_letter_to_text should return the same string when given a string."""
    assert letter_writer.render_letter_to_text("Hello") == "Hello"


def test_letter_render_to_text_with_dict():
    """render_letter_to_text should format dict key/value pairs into lines."""
    sample_data = {"field1": "value1", "field2": "value2"}
    output = letter_writer.render_letter_to_text(sample_data)
    assert "field1: value1" in output
    assert "field2: value2" in output


def test_letter_bundle_all_letters_invalid_type():
    """bundle_all_letters should return error message and None doc_id for unsupported types."""
    content, doc_id = letter_writer.bundle_all_letters(123, document_type="UNKNOWN")
    assert content == "Document type not supported"
    assert doc_id is None
