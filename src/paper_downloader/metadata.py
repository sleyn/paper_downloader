"""Paper folder naming."""

import re


def make_folder_name(year: str, author: str, journal: str) -> str:
    journal_slug = re.sub(r"[^a-zA-Z0-9]", "", journal)
    return f"{year}_{author}_{journal_slug}"


def unique_name(base: str, seen: dict) -> str:
    """Return a unique name by appending _2, _3, … if base already used."""
    if base not in seen:
        seen[base] = 1
        return base
    seen[base] += 1
    return f"{base}_{seen[base]}"
