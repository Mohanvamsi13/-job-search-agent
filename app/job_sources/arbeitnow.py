"""Client for Arbeitnow's free, public job board API.

No API key needed. Docs: https://www.arbeitnow.com/api/job-board-api
This is a pure data-fetching step - no LLM calls here, so it's free and
fast regardless of how many jobs you pull. Filtering/scoring against your
resume also happens without an LLM call (see app/job_matcher.py) - the LLM
is only used later, once you pick a specific job to tailor for.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.models import JobListing

BASE_URL = "https://www.arbeitnow.com/api/job-board-api"


def _parse_posted_at(raw) -> Optional[datetime]:
    """Arbeitnow's created_at has been seen as both a unix timestamp (int)
    and an ISO 8601 string depending on the listing - handle both, return
    None if it can't be parsed rather than guessing."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(raw, tz=timezone.utc)
        except (ValueError, OSError):
            return None
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def fetch_jobs(
    keyword: str = "",
    location: str = "",
    remote_only: bool = False,
    posted_within_days: Optional[int] = None,
    max_pages: int = 5,
) -> list[JobListing]:
    """Fetches jobs from Arbeitnow, filtered client-side (the API itself
    doesn't support server-side keyword/location/date search):

    - keyword: must appear in title, tags, or description (case-insensitive)
    - location: must appear in the listing's location field (case-insensitive)
    - posted_within_days: only keep jobs posted on/after (today - N days).
      Pass 0 to mean "today only".
    - remote_only: only keep listings marked remote

    Results are sorted most-recently-posted first.
    """
    listings: list[JobListing] = []
    keyword_lower = keyword.lower().strip()
    location_lower = location.lower().strip()

    # Arbeitnow's location field is city-level (e.g. "Berlin"), so a
    # country-level term like "Germany" would never match anything even
    # though nearly every listing IS in Germany/Austria/Switzerland. Treat
    # country-level terms as "no city filter" rather than a guaranteed miss.
    _country_terms = {"germany", "deutschland", "de", "austria", "österreich",
                       "at", "switzerland", "schweiz", "ch"}
    if location_lower in _country_terms:
        location_lower = ""

    cutoff = None
    if posted_within_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=posted_within_days)
        cutoff = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)

    with httpx.Client(timeout=15.0) as client:
        for page in range(1, max_pages + 1):
            try:
                resp = client.get(BASE_URL, params={"page": page})
                resp.raise_for_status()
            except httpx.HTTPError:
                break
            payload = resp.json()
            data = payload.get("data", [])
            if not data:
                break

            for item in data:
                title = item.get("title", "")
                tags = item.get("tags", []) or []
                description = item.get("description", "") or ""
                is_remote = bool(item.get("remote", False))
                job_location = item.get("location", "") or ""
                posted_dt = _parse_posted_at(item.get("created_at"))

                if remote_only and not is_remote:
                    continue

                if cutoff is not None:
                    # If we can't parse a date for this listing, skip it
                    # rather than silently including a possibly-old posting.
                    if posted_dt is None or posted_dt < cutoff:
                        continue

                if location_lower and location_lower not in job_location.lower() and not (
                    "remote" in location_lower and is_remote
                ):
                    continue

                if keyword_lower:
                    haystack = f"{title} {' '.join(tags)} {description}".lower()
                    if keyword_lower not in haystack:
                        continue

                listings.append(
                    JobListing(
                        source="arbeitnow",
                        external_id=item.get("slug", ""),
                        title=title,
                        company=item.get("company_name", ""),
                        location=job_location,
                        remote=is_remote,
                        tags=tags,
                        job_types=item.get("job_types", []) or [],
                        description=description,
                        url=item.get("url", ""),
                        posted_at=posted_dt.isoformat() if posted_dt else "",
                    )
                )

    listings.sort(key=lambda j: j.posted_at, reverse=True)
    return listings
