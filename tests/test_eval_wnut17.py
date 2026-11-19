"""The evaluation data loader must produce gold offsets that slice to the labelled names (no network needed)."""
from evaluation.wnut17 import _merge_html_escapes, _person_spans, parse_conll, rebuild


def S(*pairs):
    return list(pairs)


def spans_text(sentence):
    text, spans = rebuild(sentence)
    return text, [text[s:e] for s, e in spans]


def test_offsets_slice_to_the_labelled_names():
    sentence = S(("Meet", "O"), ("John", "B-person"), ("Smith", "I-person"), ("at", "O"), ("Paris", "B-location"), (".", "O"))
    text, names = spans_text(sentence)
    assert text == "Meet John Smith at Paris." and names == ["John Smith"]


def test_punctuation_and_clitics_attach_without_a_space():
    sentence = S(("Anna", "B-person"), ("'s", "O"), ("friend", "O"), (",", "O"), ("Bob", "B-person"), ("!", "O"))
    text, names = spans_text(sentence)
    assert text == "Anna's friend, Bob!" and names == ["Anna", "Bob"]


def test_adjacent_entities_are_separate_spans():
    sentence = S(("Ann", "B-person"), ("Lee", "B-person"), ("won", "O"))
    assert spans_text(sentence)[1] == ["Ann", "Lee"]


def test_i_tag_without_b_starts_a_span_and_trailing_span_is_closed():
    sentence = S(("hello", "O"), ("Maria", "I-person"), ("Garcia", "I-person"))
    assert spans_text(sentence)[1] == ["Maria Garcia"]


def test_other_entity_types_are_not_persons():
    sentence = S(("Apple", "B-corporation"), ("hired", "O"), ("Ann", "B-person"), ("in", "O"), ("Paris", "B-location"))
    assert spans_text(sentence)[1] == ["Ann"]


def test_reddit_html_escapes_are_restored_and_do_not_shift_offsets():
    sentence = S(("&", "O"), ("gt", "O"), (";", "O"), ("Tom", "B-person"), ("said", "O"))
    text, names = spans_text(sentence)
    assert text.startswith(">") and names == ["Tom"]
    assert _merge_html_escapes([("a", "O")]) == [("a", "O")]


def test_split_apostrophes_are_rejoined_and_offsets_stay_correct():
    sentence = S(("I", "O"), ("wo", "O"), ("n", "O"), ("'", "O"), ("t", "O"), ("trust", "O"), ("Putin", "B-person"),
                 ("'", "O"), ("s", "O"), ("boy", "O"))
    text, names = spans_text(sentence)
    assert text == "I won't trust Putin's boy" and names == ["Putin"]


def test_a_lone_apostrophe_not_followed_by_a_clitic_is_left_alone():
    sentence = S(("O", "B-person"), ("'", "I-person"), ("Brien", "I-person"))
    assert spans_text(sentence)[1] == ["O ' Brien"]


def test_non_ascii_names_use_code_point_offsets():
    sentence = S(("😀", "O"), ("José", "B-person"), ("Núñez", "I-person"), ("🎉", "O"))
    text, names = spans_text(sentence)
    assert names == ["José Núñez"] and text.index("José") == 2


def test_person_spans_from_tags_alone():
    assert _person_spans(["O", "B-person", "I-person", "O"], [(0, 1), (2, 3), (4, 5), (6, 7)]) == [(2, 5)]
    assert _person_spans([], []) == []


def test_parse_conll_splits_sentences_on_blank_lines(tmp_path):
    path = tmp_path / "x.conll"
    path.write_text("a\tO\nBob\tB-person\n\nb\tO\n\n", encoding="utf-8")
    assert parse_conll(path) == [[("a", "O"), ("Bob", "B-person")], [("b", "O")]]
