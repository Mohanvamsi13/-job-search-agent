"""Small shared helper used by both German-format document writers.

Extracting "the city" from a free-text address is harder than it looks:
addresses get typed in different orders (Street, PostalCode, City, Country
vs. Street, PostalCode City, Country vs. just City). This handles the
common German formats without guessing at anything not actually present
in the address text.
"""
import re

_COUNTRY_NAMES = {
    "germany", "deutschland", "austria", "österreich",
    "switzerland", "schweiz",
}


def extract_city(location: str) -> str:
    """Best-effort extraction of a city name from a free-text address.
    Returns "" if nothing identifiable is found - callers should fall back
    to a placeholder rather than guessing."""
    if not location:
        return ""

    parts = [p.strip() for p in location.split(",") if p.strip()]
    if not parts:
        return ""

    if parts[-1].lower() in _COUNTRY_NAMES:
        parts = parts[:-1]
    if not parts:
        return ""

    last = parts[-1]
    # Strip a leading postal code if present, e.g. "50765 Koeln" -> "Koeln"
    match = re.match(r"^\d{4,6}\s+(.+)$", last)
    if match:
        return match.group(1).strip()

    # If the last segment is itself just a postal code with nothing after
    # it (e.g. the address was "Street, PostalCode, City" but City got cut
    # off somehow), fall back to the second-to-last segment if it's not
    # purely numeric (a street number).
    if re.match(r"^\d{4,6}$", last) and len(parts) >= 2:
        candidate = parts[-2]
        if not re.match(r"^[\d\s.\-]+$", candidate):
            return candidate

    return last
