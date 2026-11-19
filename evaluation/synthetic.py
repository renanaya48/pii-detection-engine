"""Seeded synthetic evaluation data with a STRUCTURAL dev/test split.

Different random seeds alone would leave dev and test sharing every template and only swapping names and
numbers, so test would mostly re-measure templates the engine was tuned on. Here the two splits share NO
templates, name pools, email styles, card layouts, or hard-negative kinds (tests/test_eval_synthetic.py
enforces it). Test is therefore also a held-out-FORMAT check: lower scores there are expected and informative.

Usage (repo root):
    python -m evaluation.synthetic build            # writes evaluation/data/synthetic_{dev,test}.jsonl

Record: {"id", "source", "group", "text", "gold": [{"type","start","end"}], "region": str|null,
         "expected_status": "partial"|null}
* gold spans never include titles ("Dr.") or surrounding punctuation.
* "region" is passed to the engine as the caller's region hint (needed for national phone formats).
* non-English records contain PERSON gold the English-only NER is NOT expected to find: they measure the
  documented coverage gap, and their groups are reported separately from English PERSON recall.
The regression examples in tests/ were used to fix the engine, so they count as DEV data.
"""
from __future__ import annotations

import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import phonenumbers

DATA = Path(__file__).parent / "data"
SEEDS = {"dev": 101, "test": 202}
PER_GROUP = {"dev": 24, "test": 24}
_SLOT = re.compile(r"\[\[(\w+)\]\]")


@dataclass(frozen=True)
class Pools:
    first: tuple[str, ...]
    last: tuple[str, ...]
    domains: tuple[str, ...]
    email_styles: tuple[str, ...]
    person_styles: tuple[str, ...]
    card_styles: tuple[str, ...]
    phone_styles: tuple[str, ...]
    places: tuple[str, ...]
    orgs: tuple[str, ...]
    products: tuple[str, ...]
    negatives: tuple[str, ...]  # kinds of PII look-alikes
    es_first: tuple[str, ...] = ()
    es_last: tuple[str, ...] = ()
    fr_first: tuple[str, ...] = ()
    fr_last: tuple[str, ...] = ()
    he_names: tuple[str, ...] = ()
    other_card_prefixes: tuple[str, ...] = ()  # real card brands this engine does not know (Maestro, Mir, RuPay, Troy)
    id_prefixes: tuple[str, ...] = ()  # leading digits of 16-digit order numbers that happen to pass Luhn
    phone_suffixes: tuple[str, ...] = ()  # digits written after a phone number
    chain_styles: tuple[str, ...] = ()  # layouts of random '+' digit chains (not phone numbers)


POOLS = {
    "dev": Pools(
        first=("Emily", "Michael", "Sarah", "David", "Jessica", "Daniel", "Laura", "Robert", "Anna", "Thomas", "Olivia", "James"),
        last=("Carter", "Johnson", "Thompson", "Miller", "Brown", "Wilson", "Allen", "Walker", "Hall", "Young", "Baker", "Scott"),
        domains=("example.com", "mail.example.org", "corp.example.net"),
        email_styles=("first.last", "first_last", "initial.last"),
        person_styles=("full", "title", "single"),
        card_styles=("spaced", "visa_mc"),
        phone_styles=("international",),
        places=("New York", "London", "Chicago", "Boston"),
        orgs=("Acme Corp", "Globex", "Initech", "Umbrella Group"),
        products=("Windows Server", "Excel", "Photoshop"),
        negatives=("date", "version", "order", "uuid"),
        es_first=("Lucía", "Carlos", "Marta", "Javier"),
        es_last=("Fernández", "Martínez", "Gómez", "Ruiz"),
        fr_first=("Camille", "Julien", "Sophie", "Nicolas"),
        fr_last=("Dubois", "Martin", "Lefèvre", "Moreau"),
        he_names=("דוד כהן", "שרה לוי", "יוסי מזרחי"),
        other_card_prefixes=("5018", "2202"),
        id_prefixes=("1", "7", "9"),
        phone_suffixes=(" 12", " 123456"),
        chain_styles=("spaces",),
    ),
    "test": Pools(  # nothing here appears in the dev pools
        first=("Priya", "Mohammed", "Chen", "Fatima", "Lars", "Aiko", "Kwame", "Ingrid", "Rafael", "Yusuf", "Nadia", "Dmitri"),
        last=("Patel", "Okafor", "Nakamura", "Haddad", "Lindqvist", "Oyelaran", "Kowalski", "Bianchi", "Tanaka", "Silva", "Novak", "Bergstrom"),
        domains=("northwind.io", "post.finance.example", "studio-24.example.co.uk", "dept.univ.example.edu"),
        email_styles=("first-last", "plus_tag", "name_digits", "unicode"),
        person_styles=("lower", "caps", "surname_first", "full"),
        card_styles=("hyphen", "unbroken", "amex"),
        phone_styles=("e164", "international"),
        places=("San Francisco", "Berlin", "Toronto", "Mumbai"),
        orgs=("Contoso", "Fabrikam", "Wayne Enterprises", "Stark Industries"),
        products=("Prime Minister", "Windows Defender", "Google Maps", "Black Friday"),
        negatives=("hash", "isbn", "ipv4", "tracking", "luhn_invalid", "range"),
        es_first=("Isabel", "Diego", "Valentina", "Andrés"),
        es_last=("Herrera", "Castillo", "Navarro", "Ortega"),
        fr_first=("Élodie", "Thomas", "Margaux", "Baptiste"),
        fr_last=("Garnier", "Girard", "Roussel", "Fontaine"),
        he_names=("נועה ברק", "אורי שמש", "מיכל גולן"),
        other_card_prefixes=("6759", "9792"),
        id_prefixes=("8", "2999", "0"),
        phone_suffixes=(" 2024", " 77 88"),
        chain_styles=("hyphens", "brackets"),
    ),
}

# Templates use [[SLOT]]; slots are filled by providers below. DEV and TEST share none of these strings.
TEMPLATES: dict[str, dict[str, list[str]]] = {
    "email": {
        "dev": ["Please send the report to [[EMAIL]] before Friday.", "You can reach support at [[EMAIL]] any time.", "My address is [[EMAIL]], thanks."],
        "test": ["Forward this to <[[EMAIL]]> please.", "email: [[EMAIL]]", "Cc: [[EMAIL]]; [[EMAIL]]"],
    },
    "phone_international": {
        "dev": ["Call me on [[PHONE]] after lunch.", "The office number is [[PHONE]]."],
        "test": ["Tel. [[PHONE]] (mobile)", "WhatsApp: [[PHONE]] or [[PHONE]]"],
    },
    "phone_national_with_region": {
        "dev": ["Ring [[PHONE]] when you arrive."],
        "test": ["Hotline [[PHONE]], open until six."],
    },
    "phone_national_no_region": {  # by design NOT detected without a region hint: measures that choice
        "dev": ["Ring [[PHONE]] when you arrive."],
        "test": ["Hotline [[PHONE]], open until six."],
    },
    "card": {
        "dev": ["The payment used card [[CARD]] yesterday.", "Please charge [[CARD]] for the renewal."],
        "test": ["Card on file: [[CARD]].", "Billing -> [[CARD]] (expires next year)"],
    },
    "card_digit_context": {  # digits next to a card: a prefix or suffix of unrelated numbers
        "dev": ["Ref 12 34 56 [[CARD]] thanks", "[[CARD]] 123"],
        "test": ["order 9981-22 [[CARD]]", "[[CARD]] 12/27"],
    },
    "card_other_brand": {  # real cards whose brand prefix this engine does not know: balanced misses them by design
        "dev": ["Please charge the Maestro card [[OTHERCARD]] today.", "[[OTHERCARD]] is the number on the card."],
        "test": ["Debit card: [[OTHERCARD]]", "Paid with [[OTHERCARD]] at the till."],
    },
    "phone_digit_suffix": {  # a valid international number followed by more digits: strict recovers it
        "dev": ["Call [[PHONESUFFIX]] after lunch.", "The office line is [[PHONESUFFIX]]."],
        "test": ["Tel: [[PHONESUFFIX]]", "Reach me on [[PHONESUFFIX]], thanks."],
    },
    "negative_luhn_ids": {  # 16-digit order numbers that pass Luhn but are not cards: the cost of strict's card rule
        "dev": ["Order number [[LUHNID]] has shipped.", "Your reference is [[LUHNID]]."],
        "test": ["Tracking id: [[LUHNID]]", "Invoice [[LUHNID]] is overdue."],
    },
    "negative_plus_chains": {  # random '+' digit chains that are not phone numbers: the cost of strict's phone recovery
        "dev": ["The code was [[PLUSCHAIN]] in the log.", "He scored [[PLUSCHAIN]] overall."],
        "test": ["checksum -> [[PLUSCHAIN]]", "Result: [[PLUSCHAIN]] (final)"],
    },
    "person": {
        "dev": ["Yesterday [[PERSON]] called about the contract.", "The report was reviewed by [[PERSON]] and approved.", "[[PERSON]] will join the meeting."],
        "test": ["Notes taken by [[PERSON]]:", "thanks again, [[PERSON]]!", "Attendees: [[PERSON]], [[PERSON]]"],
    },
    "mixed": {
        "dev": ["Please send the invoice to [[PERSON]] at [[EMAIL]], or call [[PHONE]].", "Hi, my name is [[PERSON]] and my card is [[CARD]]."],
        "test": ["From: [[PERSON]] <[[EMAIL]]>\nTel: [[PHONE]]", '{"name": "[[PERSON]]", "email": "[[EMAIL]]", "card": "[[CARD]]"}', "| [[PERSON]] | [[EMAIL]] | [[PHONE]] |"],
    },
    "negative_numbers": {
        "dev": ["The meeting is on [[NEG]] in room 4.", "Release [[NEG]] shipped on schedule."],
        "test": ["ref: [[NEG]]", "See item [[NEG]] in the attached list."],
    },
    "negative_capitalised": {
        "dev": ["We are moving the team to [[PLACE]] next spring.", "[[ORG]] announced the results this morning."],
        "test": ["I just bought [[PRODUCT]] for my laptop.", "The deal with [[ORG]] closes in [[PLACE]]."],
    },
    "negative_prose": {
        "dev": ["The quarterly report was reviewed and the team agreed to move the deadline to next week.", "Please make sure the documentation is updated before the release goes out."],
        "test": ["lol that was the funniest thing i have seen all week", "Remember to back up the shared folder before the maintenance window."],
    },
    "nonenglish_es": {
        "dev": ["Ayer [[PERSON]] llamó para hablar del contrato, su correo es [[EMAIL]].", "Por favor envía la factura al [[PHONE]] y cobra la tarjeta [[CARD]]."],
        "test": ["Hola, soy [[PERSON]] y mi teléfono es [[PHONE]] para el pedido.", "El pago se hizo con la tarjeta [[CARD]] a nombre de [[PERSON]]."],
    },
    "nonenglish_fr": {
        "dev": ["Hier, [[PERSON]] a appelé au sujet du contrat, son e-mail est [[EMAIL]].", "Merci d'envoyer la facture au [[PHONE]] pour la carte [[CARD]]."],
        "test": ["Bonjour, je suis [[PERSON]] et mon numéro est [[PHONE]] pour la commande.", "Le paiement a été fait avec la carte [[CARD]] au nom de [[PERSON]]."],
    },
    "nonenglish_he": {
        "dev": ["שלום, אני רוצה לשלוח את החשבונית ל[[PERSON]], המייל שלו [[EMAIL]]"],
        "test": ["תודה רבה, [[PERSON]] ביקש שנתקשר למספר [[PHONE]] לגבי ההזמנה"],
    },
}
EXPECTED_PARTIAL = {"nonenglish_es", "nonenglish_fr", "nonenglish_he"}
REGION = {"phone_national_with_region", "phone_national_no_region"}  # groups whose phones use a national format
REGIONS = ("US", "GB", "DE", "FR", "ES", "IL", "IN", "AU")


# ---- providers: each returns (surface text, entity type or None) --------------------------------

def _luhn_digit(prefix: str) -> str:
    total = 0
    for i, ch in enumerate(reversed(prefix)):  # the check digit sits to the right of ``prefix``
        d = int(ch)
        if i % 2 == 0:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return str((10 - total % 10) % 10)


def _card_digits(rnd: random.Random, brand: str) -> str:
    body = {"visa": "4" + _rand_digits(rnd, 14), "mastercard": "5" + str(rnd.randint(1, 5)) + _rand_digits(rnd, 13),
            "discover": "6011" + _rand_digits(rnd, 11), "amex": "3" + rnd.choice("47") + _rand_digits(rnd, 12)}[brand]
    return body + _luhn_digit(body)


def _rand_digits(rnd: random.Random, n: int) -> str:
    return "".join(rnd.choice("0123456789") for _ in range(n))


def _group(digits: str, size: int = 4, sep: str = " ") -> str:
    return sep.join(digits[i : i + size] for i in range(0, len(digits), size))


def card(rnd, pools, valid=True):
    style = rnd.choice(pools.card_styles)
    brand = "amex" if style == "amex" else rnd.choice(["visa", "mastercard", "discover"] if style != "visa_mc" else ["visa", "mastercard"])
    digits = _card_digits(rnd, brand)
    if not valid:
        digits = digits[:-1] + str((int(digits[-1]) + 1 + rnd.randint(0, 8)) % 10)
    if style == "amex":
        return f"{digits[:4]} {digits[4:10]} {digits[10:]}"
    if style == "hyphen":
        return _group(digits, 4, "-")
    if style == "unbroken":
        return digits
    return _group(digits)  # "spaced" and "visa_mc"


def _format_card(digits: str, style: str) -> str:
    return {"hyphen": _group(digits, 4, "-"), "unbroken": digits}.get(style, _group(digits))


def other_brand_card(rnd, pools):
    """A Luhn-valid 16-digit number whose prefix belongs to a brand outside the engine's brand table."""
    body = rnd.choice(pools.other_card_prefixes) + _rand_digits(rnd, 11)
    return _format_card(body + _luhn_digit(body), rnd.choice(pools.card_styles))


def luhn_valid_id(rnd, pools):
    """A 16-digit order/tracking number that passes Luhn by construction and has no known card prefix."""
    body = rnd.choice(pools.id_prefixes)
    body += _rand_digits(rnd, 15 - len(body))
    return _format_card(body + _luhn_digit(body), rnd.choice(pools.card_styles))


def plus_chain(rnd, pools):
    """'+' followed by random digit groups: looks like an international number, is not one."""
    style = rnd.choice(pools.chain_styles)
    groups = [_rand_digits(rnd, rnd.randint(1, 4)) for _ in range(rnd.randint(4, 7))]
    first = rnd.choice("123456789")
    if style == "hyphens":
        return f"+{first}-" + "-".join(groups)
    if style == "brackets":
        return f"+{first} ({groups[0]}) " + " ".join(groups[1:])
    return f"+{first} " + " ".join(groups)


def person(rnd, pools):
    first, last = rnd.choice(pools.first), rnd.choice(pools.last)
    style = rnd.choice(pools.person_styles)
    return {"full": f"{first} {last}", "title": f"{first} {last}", "single": first, "lower": f"{first} {last}".lower(),
            "caps": f"{first} {last}".upper(), "surname_first": f"{last}, {first}"}[style], style


def email(rnd, pools):
    first, last = rnd.choice(pools.first).lower(), rnd.choice(pools.last).lower()
    first, last = _ascii(first), _ascii(last)
    domain = rnd.choice(pools.domains)
    local = {"first.last": f"{first}.{last}", "first_last": f"{first}_{last}", "initial.last": f"{first[0]}.{last}",
             "first-last": f"{first}-{last}", "plus_tag": f"{first}+news", "name_digits": f"{last}{rnd.randint(10, 99)}",
             "unicode": f"josé.{last}"}[rnd.choice(pools.email_styles)]
    return f"{local}@{domain}"


def _ascii(s: str) -> str:
    return s.encode("ascii", "ignore").decode() or "user"


def phone(rnd, pools, national=False, region=None):
    region = region or rnd.choice(REGIONS)
    example = phonenumbers.example_number(region)
    length = len(str(example.national_number))
    for _ in range(500):  # random digits with the example's length, kept only if the number is valid
        candidate = int(str(example.national_number)[0] + _rand_digits(rnd, length - 1))
        number = phonenumbers.PhoneNumber(country_code=example.country_code, national_number=candidate)
        if phonenumbers.is_valid_number(number):
            break
    else:
        number = example
    if national:
        return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.NATIONAL)
    style = rnd.choice(pools.phone_styles)
    fmt = phonenumbers.PhoneNumberFormat.E164 if style == "e164" else phonenumbers.PhoneNumberFormat.INTERNATIONAL
    return phonenumbers.format_number(number, fmt)


def negative_number(rnd, pools):
    kind = rnd.choice(pools.negatives)
    hexdigits = "0123456789abcdef"
    return {
        "date": f"2024-{rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d}",
        "version": f"{rnd.randint(1, 9)}.{rnd.randint(0, 20)}.{rnd.randint(0, 30)}",
        "order": f"{rnd.randint(1000, 9999)}-{rnd.randint(1000, 9999)}",
        "uuid": "-".join("".join(rnd.choice(hexdigits) for _ in range(n)) for n in (8, 4, 4, 4, 12)),
        "hash": "".join(rnd.choice(hexdigits) for _ in range(40)),
        "isbn": f"978-{rnd.randint(0, 9)}-{_rand_digits(rnd, 5)}-{_rand_digits(rnd, 3)}-{rnd.randint(0, 9)}",
        "ipv4": ".".join(str(rnd.randint(1, 254)) for _ in range(4)),
        "tracking": f"1Z999AA1{_rand_digits(rnd, 10)}",
        "luhn_invalid": card(rnd, pools, valid=False),
        "range": f"{rnd.randint(2015, 2019)}-{rnd.randint(2020, 2024)}-{rnd.randint(2025, 2030)}",
    }[kind]


def build_record(rnd: random.Random, split: str, group: str, template: str, index: int) -> dict:
    pools = POOLS[split]
    # National formats need a country to be written; only one group also tells the ENGINE that country.
    # "phone_national_no_region" is scanned without a hint, to measure the design choice of not guessing.
    format_region = rnd.choice(REGIONS) if group in REGION else None
    region = format_region if group == "phone_national_with_region" else None
    parts: list[str] = []
    gold: list[dict] = []
    length = 0
    pos = 0
    name_pool = {"nonenglish_es": (pools.es_first, pools.es_last), "nonenglish_fr": (pools.fr_first, pools.fr_last)}.get(group)

    def emit(surface: str, entity: str | None) -> None:
        nonlocal length
        if entity:
            gold.append({"type": entity, "start": length, "end": length + len(surface)})
        parts.append(surface)
        length += len(surface)

    for match in _SLOT.finditer(template):
        emit(template[pos : match.start()], None)
        pos = match.end()
        slot = match.group(1)
        if slot == "EMAIL":
            emit(email(rnd, pools), "EMAIL")
        elif slot == "PHONE":
            emit(phone(rnd, pools, national=group in REGION, region=format_region), "PHONE")
        elif slot == "CARD":
            emit(card(rnd, pools), "CREDIT_CARD")
        elif slot == "OTHERCARD":
            emit(other_brand_card(rnd, pools), "CREDIT_CARD")
        elif slot == "LUHNID":
            emit(luhn_valid_id(rnd, pools), None)
        elif slot == "PLUSCHAIN":
            emit(plus_chain(rnd, pools), None)
        elif slot == "PHONESUFFIX":
            number = phone(rnd, pools, national=False, region=None)
            emit(number, "PHONE")  # the suffix is context, not part of the number
            emit(rnd.choice(pools.phone_suffixes), None)
        elif slot == "PERSON":
            if group == "nonenglish_he":
                emit(rnd.choice(pools.he_names), "PERSON")
            elif name_pool:
                emit(f"{rnd.choice(name_pool[0])} {rnd.choice(name_pool[1])}", "PERSON")
            else:
                surface, style = person(rnd, pools)
                if style == "title":
                    emit("Dr. ", None)  # the title is context, not part of the name
                emit(surface, "PERSON")
        elif slot == "NEG":
            emit(negative_number(rnd, pools), None)
        elif slot == "PLACE":
            emit(rnd.choice(pools.places), None)
        elif slot == "ORG":
            emit(rnd.choice(pools.orgs), None)
        elif slot == "PRODUCT":
            emit(rnd.choice(pools.products), None)
        else:
            raise ValueError(f"unknown slot {slot}")
    emit(template[pos:], None)
    text = "".join(parts)
    for g in gold:
        assert text[g["start"] : g["end"]].strip(), (group, text)
    return {"id": f"syn-{split}-{group}-{index}", "source": f"synthetic-{split}", "group": group, "text": text, "gold": gold,
            "region": region, "expected_status": "partial" if group in EXPECTED_PARTIAL else None}


def build_split(split: str) -> list[dict]:
    rnd = random.Random(SEEDS[split])
    records = []
    for group, by_split in TEMPLATES.items():
        templates = by_split[split]
        for i in range(PER_GROUP[split]):
            records.append(build_record(rnd, split, group, templates[i % len(templates)], i))
    return records


def build() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    for split in ("dev", "test"):
        records = build_split(split)
        out = DATA / f"synthetic_{split}.jsonl"
        with out.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        entities = sum(len(r["gold"]) for r in records)
        print(f"{split}: {len(records)} records, {entities} gold entities, {len(TEMPLATES)} groups -> {out}")


if __name__ == "__main__":
    if sys.argv[1:] == ["build"]:
        build()
    else:
        raise SystemExit(__doc__)
