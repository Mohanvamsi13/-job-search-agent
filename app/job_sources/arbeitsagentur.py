"""Client for the Bundesagentur für Arbeit (Arbeitsagentur) Jobsuche API.

This is Germany's official federal employment agency job board - the
largest free, legitimate job data source available for this app. No API
key signup is needed: the "X-API-Key" value below is the public client ID
used by Arbeitsagentur's own mobile app, openly documented by the
community-maintained bundesAPI/jobsuche-api project (a well-known reference
for this officially-public-but-informally-documented API). This is not a
scraper - it calls the same REST endpoint the official app calls.

One quirk: the search endpoint returns title/employer/location but NOT the
full job description. Getting the full text requires a second call per job
using its reference number. To avoid hundreds of extra calls for jobs
nobody selects, fetch_job_description() is only called lazily, when a
specific job gets chosen for tailoring (see streamlit_app.py).
"""
import base64
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.models import JobListing

BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc"
HEADERS = {"X-API-Key": "jobboerse-jobsuche"}


def fetch_jobs(
    keyword: str = "",
    location: str = "",
    remote_only: bool = False,
    posted_within_days: Optional[int] = None,
    max_pages: int = 3,
    page_size: int = 25,
) -> list[JobListing]:
    """Searches Arbeitsagentur's job board. remote_only is applied
    client-side (the API doesn't have a direct "remote" filter; "ho" /
    home-office is requested via arbeitszeit, but coverage is inconsistent,
    so we still double check locally for safety)."""
    listings: list[JobListing] = []

    params = {
        "page": 1,
        "size": page_size,
        "pav": "false",
    }
    if keyword.strip():
        params["was"] = keyword.strip()
    if location.strip():
        params["wo"] = location.strip()
        params["umkreis"] = 100
    if posted_within_days is not None:
        params["veroeffentlichtseit"] = max(0, min(100, posted_within_days))

    with httpx.Client(timeout=15.0, headers=HEADERS) as client:
        for page in range(1, max_pages + 1):
            params["page"] = page
            try:
                resp = client.get(f"{BASE_URL}/v4/jobs", params=params)
                resp.raise_for_status()
            except httpx.HTTPError:
                break

            payload = resp.json()
            items = payload.get("stellenangebote", [])
            if not items:
                break

            for item in items:
                arbeitsort = item.get("arbeitsort", {}) or {}
                city = arbeitsort.get("ort", "")
                is_remote = "homeoffice" in str(item.get("arbeitszeit", "")).lower()

                if remote_only and not is_remote:
                    continue

                refnr = item.get("refnr", "")
                external_url = item.get("externeUrl", "")
                detail_url = external_url or (
                    f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}" if refnr else ""
                )

                published = item.get("aktuelleVeroeffentlichungsdatum", "")
                posted_at = ""
                if published:
                    try:
                        posted_at = datetime.fromisoformat(published).replace(
                            tzinfo=timezone.utc
                        ).isoformat()
                    except ValueError:
                        posted_at = published  # keep raw value rather than dropping it

                listings.append(
                    JobListing(
                        source="arbeitsagentur",
                        external_id=refnr,
                        title=item.get("titel", ""),
                        company=item.get("arbeitgeber", ""),
                        location=city,
                        remote=is_remote,
                        tags=[],
                        job_types=[],
                        description="",  # fetched lazily - see fetch_job_description()
                        url=detail_url,
                        posted_at=posted_at,
                    )
                )

            if len(items) < page_size:
                break  # last page

    return listings


def fetch_job_description(refnr: str) -> str:
    """Fetches the full job description text for one listing, given its
    reference number. Called only when a job is actually selected for
    tailoring, not for every search result."""
    if not refnr:
        return ""
    encoded = base64.b64encode(refnr.encode()).decode()
    try:
        with httpx.Client(timeout=15.0, headers=HEADERS) as client:
            resp = client.get(f"{BASE_URL}/v4/jobdetails/{encoded}")
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        return ""

    # Field name per community documentation; fall back gracefully if the
    # API's response shape differs from what's documented.
    return data.get("stellenbeschreibung", "") or data.get("beschreibung", "") or ""
