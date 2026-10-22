"""Read-only Odoo CRM access for the sales workbench."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from minihermes.config import load_settings

OPPORTUNITY_FIELDS = ["id", "name", "commercial_partner_id", "partner_id", "stage_id"]
OPPORTUNITY_LIMIT = 50
REQUEST_TIMEOUT_SECONDS = 10


class CrmReadError(RuntimeError):
    """An Odoo CRM read failed or returned data we cannot display."""

    status_code = 502


class CrmConfigurationError(CrmReadError):
    """The server-side Odoo connection is not configured."""

    status_code = 503


def _related_name(value, field_name: str) -> str | None:
    """Return the display name from an Odoo many2one value."""
    if value is False or value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise CrmReadError(f"Odoo returned an invalid {field_name} value.")
    return str(value[1]) if value[1] is not None else None


def map_opportunity(record: dict) -> dict:
    """Convert one Odoo crm.lead opportunity into the workbench card shape."""
    if not isinstance(record, dict) or "id" not in record or "name" not in record:
        message = "Odoo returned an invalid opportunity record."
        raise CrmReadError(message)

    return {
        "id": record["id"],
        "name": str(record["name"] or ""),
        "customer_name": _related_name(
            # Odoo 19 only sets commercial_partner_id when the company differs
            # from partner_id (for example, a contact belonging to that company).
            record.get("commercial_partner_id") or record.get("partner_id"), "customer",
        ),
        "stage_name": _related_name(record.get("stage_id"), "stage"),
    }


def map_opportunities_response(records: list[dict]) -> dict:
    """Wrap a successful Odoo JSON-2 search_read list for the browser API."""
    if not isinstance(records, list):
        message = "Odoo returned an invalid opportunities list."
        raise CrmReadError(message)
    return {"opportunities": [map_opportunity(record) for record in records]}


def list_opportunities(settings=None, *, opener=None) -> dict:
    """Read a small list of opportunities from Odoo's JSON-2 API."""
    settings = settings or load_settings()
    base_url = (getattr(settings, "odoo_url", "") or "").strip().rstrip("/")
    api_key = (getattr(settings, "odoo_api_key", "") or "").strip()
    database = (getattr(settings, "odoo_database", "") or "").strip()

    parsed_url = urlsplit(base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        message = "Set ODOO_URL to the Odoo server base URL."
        raise CrmConfigurationError(message)
    if not api_key:
        message = "Set ODOO_API_KEY for the server-side CRM reader."
        raise CrmConfigurationError(message)

    payload = {
        "domain": [["type", "=", "opportunity"]],
        "fields": OPPORTUNITY_FIELDS,
        "limit": OPPORTUNITY_LIMIT,
        "order": "write_date desc, id desc",
    }
    headers = {
        "Authorization": f"bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "MiniHermes-CRM/1.0",
    }
    if database:
        headers["X-Odoo-Database"] = database

    request = Request(
        f"{base_url}/json/2/crm.lead/search_read",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        open_url = opener or urlopen
        with open_url(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response_body = response.read()
    except HTTPError as exc:
        raise CrmReadError(f"Odoo returned HTTP {exc.code} for the CRM read.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        message = "Could not connect to Odoo for the CRM read."
        raise CrmReadError(message) from exc

    try:
        records = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        message = "Odoo returned an invalid JSON response."
        raise CrmReadError(message) from exc

    return map_opportunities_response(records)
