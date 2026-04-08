# scripts/utils/naming.py
"""Builds Marathi + English filenames for Kishor magazine issues."""

ENG_MONTHS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]
MAR_MONTHS = [
    "", "जानेवारी", "फेब्रुवारी", "मार्च", "एप्रिल", "मे", "जून",
    "जुलै", "ऑगस्ट", "सप्टेंबर", "ऑक्टोबर", "नोव्हेंबर", "डिसेंबर"
]
_DEVANAGARI = str.maketrans("0123456789", "०१२३४५६७८९")


def parse_orig_filename(fname: str) -> tuple:
    """'2026_01.pdf' → (2026, 1). Raises ValueError on bad format."""
    base  = fname.removesuffix(".pdf")
    parts = base.split("_")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError(f"Unexpected format: {fname!r} — expected YYYY_MM.pdf")
    year, mon = int(parts[0]), int(parts[1])
    if not (1 <= mon <= 12):
        raise ValueError(f"Month out of range ({mon}) in: {fname!r}")
    if not (1990 <= year <= 2100):
        raise ValueError(f"Year out of range ({year}) in: {fname!r}")
    return year, mon


def build_friendly_filename(fname: str) -> str:
    """'2026_01.pdf' → 'किशोर जानेवारी २०२६ - Kishor January 2026.pdf'"""
    year, mon = parse_orig_filename(fname)
    return (
        f"किशोर {MAR_MONTHS[mon]} {str(year).translate(_DEVANAGARI)}"
        f" - Kishor {ENG_MONTHS[mon]} {year}.pdf"
    )


def get_clock_emoji(hour: int) -> str:
    """Return clock face emoji for hour 0–23."""
    clocks = [
        "🕛", "🕐", "🕑", "🕒", "🕓", "🕔",
        "🕕", "🕖", "🕗", "🕘", "🕙", "🕚"
    ]
    return clocks[hour % 12]
