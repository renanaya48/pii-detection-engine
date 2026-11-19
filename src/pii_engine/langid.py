"""Minimal "is this English?" check that decides whether the English NER model should run.

It is NOT a general language identifier. It answers one question and is honest about uncertainty:

* ENGLISH: English function words dominate.
* MIXED:   English plus a substantial share of another language or script.
* OTHER:   clearly not English (non-Latin script, or other-language function words dominate).
* UNCERTAIN: there are letters but no function-word signal (e.g. a bare name such as
           "María García"). The language is genuinely unknown, so the engine runs NER best-effort
           and reports PARTIAL: running the English model does not prove the text is English.
* NO_TEXT: no linguistic text remains once emails and URLs are removed (what is left is only
           numbers and symbols; the emails themselves contain letters, which is why they are
           removed first). This is deliberately NOT an unsupported language: there is nothing for
           NER to find, so pattern recognizers alone can finish the scan and the status can be
           COMPLETE.

Method: script share first (Hebrew, Cyrillic, CJK, ... are decided without any word list), then
counts of English vs. non-English function words for Latin text. Function words are frequent,
short and almost language-exclusive, so no model or memory is needed.

Known limits: short text without function words is UNCERTAIN (so short English such as
"Order ID 123456" is reported PARTIAL too); closely related languages that share function words
with English are not separated; a word list is a heuristic and will misclassify some inputs.
The engine applies the decision per segment.
"""
from __future__ import annotations

from enum import Enum

import regex

_LETTER = regex.compile(r"\p{L}")
_LATIN_LETTER = regex.compile(r"\p{Latin}")
_LATIN_WORD = regex.compile(r"\p{Latin}+")

# Emails and URLs carry no language ("com", "de", "es" are TLDs, not words) and must not vote. Only the
# address itself is removed, never the text around it: "Alice<alice@example.com>" must keep "Alice".
# (An earlier "\S+@\S+" deleted the whole space-free token, names included.) Bounded like the email
# recognizer's pattern, and the lookbehind stops it restarting inside a long run (no quadratic scan).
_NOT_LANGUAGE = regex.compile(
    r"(?<![\w.+-])[\w.+-]{1,64}@(?:[\w-]{1,63}\.){1,8}[\w-]{2,24}"
    r"|(?:https?://|www\.)[^\s<>\"'()\[\]]{1,2048}"
)

_NON_LATIN_ONLY = 0.95  # share of non-Latin letters above which text is OTHER outright
_NON_LATIN_MIXED = 0.20  # share above which text counts as MIXED even if Latin words look English
_ENGLISH_SHARE_ENGLISH = 0.80  # English share of function-word votes at/above which text is ENGLISH
_ENGLISH_SHARE_MIXED = 0.10  # below this, or with fewer than _MIN_ENGLISH_FOR_MIXED votes, text is OTHER
_MIN_ENGLISH_FOR_MIXED = 2


class Language(str, Enum):
    ENGLISH = "english"
    MIXED = "mixed"
    OTHER = "other"
    UNCERTAIN = "uncertain"  # has letters but no language signal (e.g. a bare name)
    NO_TEXT = "no_text"  # no letters at all (emails, numbers, symbols): nothing for NER to find


_ENGLISH_RAW = frozenset(
    """a about after all also an and any are as at be because been but by can could did do does for from
    had has have he her here him his how i if in into is it its just me more my no not of on one only or
    our out she so some than that the their them then there these they this to up us was we were what
    when which who will with would you your""".split()
)

# Frequent function words of common Latin-script languages.
_NON_ENGLISH_RAW = frozenset(
    """
    el la los las un una unos unas del al y o pero porque como cuando donde que quien es son está están fue
    ser hay por para con sin sobre entre desde hasta muy más menos también ya aquí allí este esta estos estas
    ese esa mi tu su nuestro vive llamó envía envíe gracias hola buenos días
    le les des du au aux et ou mais car comme quand où qui est sont été être avec sans pour dans sur sous
    très plus moins aussi déjà ici ce cette ces mon ma mes ton ta tes votre vos nous vous ils elles je tu
    merci bonjour pas ne
    der die das ein eine einen und oder aber weil wie wann wo wer ist sind wird wurde mit ohne für auf unter
    an sehr mehr auch schon hier dieser diese dieses mein dein ihr wir ich sie nicht danke hallo bitte
    il lo gli uno e ma perché come quando dove chi è sono con senza per su tra molto più anche già qui
    questo questa miei suo noi voi loro non grazie ciao
    os as um uma uns umas dos das e ou mas porque quando onde quem é são sem para sobre entre muito
    mais também já aqui este esta meu teu seu nós vocês eles elas não obrigado olá
    a an as do i in me no on or so was will
    """.split()
)
# The last line lists English function words that are ALSO very frequent in other languages
# (es/fr/it/pt "a", de "in"/"so"/"was"/"will", pt "as"/"do", es/it "no", fr "on"/"or", it "i" ...).
# They must be listed on this side too: _SHARED below only removes a word from both sides if it
# is in both lists. Missing "a" here made Spanish text count "a" as English votes, so Spanish
# looked MIXED instead of OTHER (found by the final measurement's skip counters).

# Words that are function words in English AND another listed language ("a", "an", "in"...) are
# ambiguous evidence, so they vote for neither side.
_SHARED = _ENGLISH_RAW & _NON_ENGLISH_RAW
_ENGLISH = _ENGLISH_RAW - _SHARED
_NON_ENGLISH = _NON_ENGLISH_RAW - _SHARED


def detect(text: str) -> Language:
    text = _NOT_LANGUAGE.sub(" ", text)  # emails/URLs carry no language, for script share or word votes
    letters = len(_LETTER.findall(text))
    if letters == 0:
        return Language.NO_TEXT

    non_latin_share = 1 - len(_LATIN_LETTER.findall(text)) / letters
    if non_latin_share >= _NON_LATIN_ONLY:
        return Language.OTHER
    if non_latin_share > _NON_LATIN_MIXED:
        return Language.MIXED

    english = other = 0
    for word in _LATIN_WORD.findall(text.lower()):
        if word in _ENGLISH:
            english += 1
        elif word in _NON_ENGLISH:
            other += 1
    signal = english + other
    if signal == 0:
        return Language.UNCERTAIN

    english_share = english / signal
    if english_share >= _ENGLISH_SHARE_ENGLISH:
        return Language.ENGLISH
    if english >= _MIN_ENGLISH_FOR_MIXED and english_share >= _ENGLISH_SHARE_MIXED:
        return Language.MIXED
    return Language.OTHER
