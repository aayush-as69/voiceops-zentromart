from scripts.evaluate_questions import score_answer


def test_warranty_answer_matches_unicode_whitespace():
    answer = (
        "हाँ, SKU ELE-0012 पर ZentroMart Assured लागू है। "
        "यह 12‑महीने की वारंटी है। ऐप में My\u202fOrders खोलें "
        "और Assured Warranty Claim चुनें।"
    )
    row = {
        "must_include": "12 ; My Orders / app",
        "must_not_include": "",
        "answerable": "True",
    }

    result = score_answer(answer, row)

    assert result["include_requirements_met"] is True
    assert result["correct"] is True


def test_hindi_unsupported_question_is_recognized_as_abstention():
    answer = (
        "मुझे इस विषय पर जानकारी नहीं है। "
        "क्या आप किसी मानव सहायक से बात करना चाहेंगे?"
    )
    row = {
        "must_include": (
            "don't have / do not have / not sure / no information / "
            "can't find / not able to find / couldn't find / "
            "जानकारी नहीं / pata nahi / jaankari nahi / connect / सहयोगी"
        ),
        "must_not_include": "",
        "answerable": "False",
    }

    result = score_answer(answer, row)

    assert result["include_requirements_met"] is True
    assert result["abstained"] is True
    assert result["decision_ok"] is True
    assert result["correct"] is True


def test_refund_policy_answer_is_not_misclassified_as_abstention():
    answer = (
        "I don’t have enough information to give a specific date "
        "for your refund.\n"
        "Refunds are processed within the following timeframes "
        "after they are initiated:\n"
        "| Payment method | Time to reach you |\n"
        "| UPI | 1–3 business days |\n"
        "| Credit or debit card | 5–7 business days |\n"
        "| Net banking | 3–5 business days |\n"
        "| ZentroMart Wallet | Instant, within 2 hours |\n"
        "| Bank transfer (NEFT) for COD orders | 5–7 business days |\n"
        "| ZentroMart Wallet for COD orders | Instant, within 2 hours |\n"
        "I can connect you with a human colleague."
    )
    row = {
        "must_include": "",
        "must_not_include": "",
        "answerable": "True",
    }

    result = score_answer(answer, row)

    assert result["abstained"] is False
    assert result["decision_ok"] is True
    assert result["correct"] is True