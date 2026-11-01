from src.identity_verification import extract_order_id, extract_verification_value, looks_like_order_id_only
from src.policy_rules import requires_order_lookup

def test_extract_spaced_order_id_preserves_leading_zeroes():
    assert extract_order_id("Order number is 0781 0024") == "07810024"

def test_extract_verification_values():
    assert extract_verification_value("last four digits are 0042") == "0042"
    assert extract_verification_value("delivery pincode 070091") == "070091"
    assert extract_verification_value("Order number 1234 5678") is None

def test_hinglish_and_hindi_order_help_prompts_for_id():
    assert requires_order_lookup("Hello, mujhe order ke baare mein help chahiye.")
    assert requires_order_lookup("नमस्ते, मुझे अपने ऑर्डर के बारे में मदद चाहिए।")
    assert requires_order_lookup("Hi, I need some help with an order.")


def test_order_id_only_detection_preserves_substantive_turns():
    assert looks_like_order_id_only("Order number hai 8978 2837.")
    assert looks_like_order_id_only("ऑर्डर नंबर है 7936 3550।")
    assert looks_like_order_id_only("The order number is 6649 2475.")
    assert not looks_like_order_id_only("My order 12345678 has not arrived; can I cancel it?")
    assert not looks_like_order_id_only("I need help with order 12345678")
