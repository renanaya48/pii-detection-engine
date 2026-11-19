import pytest

from pii_engine.langid import Language, detect

E, M, O, C, N = Language.ENGLISH, Language.MIXED, Language.OTHER, Language.UNCERTAIN, Language.NO_TEXT


@pytest.mark.parametrize(
    "text",
    [
        "Please send the invoice to Emily Carter before Friday.",
        "Yesterday Michael called me about the contract and he was not happy.",
        "Contact jane@example.com if you have any questions about this.",
        "The report was reviewed by Dr. Sarah Thompson.",
    ],
)
def test_english(text):
    assert detect(text) == E


@pytest.mark.parametrize(
    "text",
    [
        "Ayer Lucía Fernández llamó a Carlos para hablar del contrato y de los pagos.",
        "Hier, Camille Dubois a appelé Julien Martin au sujet du contrat avec nous.",
        "Bitte senden Sie die Rechnung an Herrn Müller und nicht an die Firma.",
        "Per favore invia la fattura a Marco Rossi prima di venerdì, grazie.",
        "Por favor envie a fatura para o João Silva antes de sexta, obrigado.",
    ],
)
def test_other_latin_script_languages(text):
    assert detect(text) == O


@pytest.mark.parametrize(
    "text",
    [
        "שלום, אני רוצה לשלוח את החשבונית לדוד כהן עד יום שישי",  # Hebrew
        "Пожалуйста, отправьте счёт Ивану Петрову до пятницы",  # Russian
        "请在周五之前把发票发给王伟",  # Chinese
        "من فضلك أرسل الفاتورة إلى أحمد علي قبل يوم الجمعة",  # Arabic
    ],
)
def test_non_latin_scripts_are_other_without_any_word_list(text):
    assert detect(text) == O


def test_english_sentence_inside_hebrew_text_is_mixed_not_other():
    text = "שלום דוד, ראיתי שהודעה נשלחה ל Emily Carter and Michael Johnson about the contract"
    assert detect(text) == M


def test_mixed_english_and_spanish_text():
    text = "Please send the invoice to Emily. Ayer llamó a Carlos para hablar del contrato y de los pagos."
    assert detect(text) == M


@pytest.mark.parametrize(
    "text",
    ["jane.doe@example.com", "+44 20 7946 0958", "4111 1111 1111 1111", "12345 67890", "", "   ", "😀😀😀"],
)
def test_no_letters_is_no_text_not_unsupported(text):
    assert detect(text) == N


@pytest.mark.parametrize(
    "text",
    [
        "Emily Carter",  # letters but no function words: the language is genuinely unknown
        "Dr. Sarah Thompson, Robert Allen",
        "María García",
        "Order ID 123456",  # short English without function words is uncertain too
    ],
)
def test_letters_without_signal_is_uncertain(text):
    assert detect(text) == C


def test_email_or_number_only_text_is_never_other():
    for text in ["a@b.com", "+1 415-555-2671", "ID 123456", "a@b.com c@d.org +34 612 345 678"]:
        assert detect(text) != O


@pytest.mark.parametrize(
    "sentence",
    [
        "Ayer Lucía Fernández llamó a Carlos Martínez para hablar del contrato y de los pagos pendientes. ",
        "Hier, Camille Dubois a appelé Julien Martin au sujet du contrat avec nous et pour les paiements. ",
        "Gestern hat Anna Müller mit Peter Schmidt über den Vertrag und die Zahlungen gesprochen, sie ist sehr froh. ",
        "Ieri Giulia Rossi ha chiamato Marco Bianchi per parlare del contratto e dei pagamenti, non è molto. ",
        "Ontem a Maria Silva ligou para o João Santos para falar do contrato e dos pagamentos, não é muito. ",
    ],
)
@pytest.mark.parametrize("size", [300, 1_000, 5_000, 20_000])
def test_repeated_non_english_text_is_other_at_every_size(sentence, size):
    """Regression: Spanish 'a' used to vote English, making long Spanish text MIXED (so NER ran on it)."""
    assert detect((sentence * (size // len(sentence) + 1))[:size]) == O


def test_words_shared_with_english_vote_for_neither_side():
    from pii_engine.langid import _SHARED

    assert _SHARED  # the overlap exists, otherwise this test proves nothing
    assert detect(" ".join(sorted(_SHARED))) == C


def test_email_in_non_english_text_does_not_dilute_the_script_share():
    assert detect("שלום, אני רוצה לשלוח את החשבונית לדוד כהן עד יום שישי a@b.com") == O


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Alice<alice@example.com>", C),  # name stuck to the address by a bracket: must not vanish
        ("Alice,alice@example.com", C),
        ("Alice:alice@example.com;Bob;bob@example.org", C),
        ('"Alice" <alice@example.com>', C),
        ("(Alice alice@example.com)", C),
        ("Alice<https://example.com/a>", C),
        ("李伟<email@example.com>", O),  # non-English name next to an address: not "no text"
        ("שלום<dudu@example.com>", O),
        ("To: Bob Smith <bob@example.com>, Carol Jones <carol@example.org>", E),  # "To" is an English word
    ],
)
def test_text_around_an_email_or_url_still_counts(text, expected):
    """Regression: the old pattern deleted the whole space-free token, so these were NO_TEXT."""
    assert detect(text) == expected


def test_only_the_address_is_removed():
    assert detect("<a@b.com>") == N and detect("a@b.com,c@d.org;e@f.net") == N


def test_email_pattern_in_the_language_check_is_linear_on_hostile_input():
    import time

    for payload in ["a@" * 50_000, "a." * 50_000, "a" * 100_000, "a@" + "b." * 50_000, "http://" + "a" * 100_000]:
        t0 = time.perf_counter()
        detect(payload)
        assert time.perf_counter() - t0 < 1.0


def test_emails_and_urls_never_vote():
    # ".com"/".de"/".es" are TLDs; "com" is also a Portuguese word.
    assert detect("x@y.com z@w.de https://www.example.com/es/") == N


def test_large_input_is_fast():
    import time

    text = "Please send the invoice to Emily Carter before Friday. " * 2000  # ~110k chars
    t0 = time.perf_counter()
    assert detect(text) == E
    assert time.perf_counter() - t0 < 0.5
