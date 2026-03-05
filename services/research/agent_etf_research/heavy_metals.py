from __future__ import annotations

import re

PERIODIC_TABLE: dict[int, tuple[str, str]] = {
    40: ("Zr", "Zirconium"),
    41: ("Nb", "Niobium"),
    42: ("Mo", "Molybdenum"),
    43: ("Tc", "Technetium"),
    44: ("Ru", "Ruthenium"),
    45: ("Rh", "Rhodium"),
    46: ("Pd", "Palladium"),
    47: ("Ag", "Silver"),
    48: ("Cd", "Cadmium"),
    49: ("In", "Indium"),
    50: ("Sn", "Tin"),
    51: ("Sb", "Antimony"),
    52: ("Te", "Tellurium"),
    72: ("Hf", "Hafnium"),
    73: ("Ta", "Tantalum"),
    74: ("W", "Tungsten"),
    75: ("Re", "Rhenium"),
    76: ("Os", "Osmium"),
    77: ("Ir", "Iridium"),
    78: ("Pt", "Platinum"),
    79: ("Au", "Gold"),
    80: ("Hg", "Mercury"),
}


def parse_atomic_ranges(text: str) -> list[tuple[int, int]]:
    lowered = text.lower()
    if "atomic" not in lowered and "periodic" not in lowered:
        return []

    ranges: list[tuple[int, int]] = []
    for start_text, end_text in re.findall(r"(\d{1,3})\s*-\s*(\d{1,3})", text):
        start = int(start_text)
        end = int(end_text)
        if start > end:
            start, end = end, start
        ranges.append((start, end))
    return ranges


def derive_heavy_metal_profile(text: str) -> dict[str, object] | None:
    ranges = parse_atomic_ranges(text)
    if not ranges:
        return None

    atomic_numbers: list[int] = []
    for start, end in ranges:
        atomic_numbers.extend(
            number for number in range(start, end + 1) if number in PERIODIC_TABLE
        )

    if not atomic_numbers:
        return None

    symbols = [PERIODIC_TABLE[number][0] for number in atomic_numbers]
    names = [PERIODIC_TABLE[number][1] for number in atomic_numbers]

    return {
        "theme": "heavy_metals_periodic_table",
        "atomic_ranges": ranges,
        "atomic_numbers": atomic_numbers,
        "element_symbols": symbols,
        "element_names": names,
    }
