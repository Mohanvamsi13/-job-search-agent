"""Generates pre-filled job search URLs for platforms that don't offer a
public API (LinkedIn, Indeed, StepStone, Xing). This deliberately does NOT
scrape these sites - that would violate their terms of service and risk
getting blocked. Instead it builds the exact URL their own search bar would
produce, so one click takes you to a real, live, already-filtered results
page on that platform.
"""
from urllib.parse import quote_plus


def build_quick_links(keyword: str, location: str = "") -> dict[str, str]:
    kw = quote_plus(keyword.strip()) if keyword.strip() else ""
    loc = quote_plus(location.strip()) if location.strip() else ""

    links = {
        "LinkedIn": f"https://www.linkedin.com/jobs/search/?keywords={kw}&location={loc}",
        "Indeed": f"https://de.indeed.com/jobs?q={kw}&l={loc}",
        "StepStone": f"https://www.stepstone.de/5/ergebnisliste.html?ke={kw}&ws={loc}",
        "Xing": f"https://www.xing.com/jobs/search?keywords={kw}&location={loc}",
    }
    return links
