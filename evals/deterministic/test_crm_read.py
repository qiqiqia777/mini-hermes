import json
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from minihermes.ops import crm_read, dashboard

RECORD = {
    "id": 417,
    "name": "华东客户扫码枪急单跟进",
    "commercial_partner_id": [208, "华东办公设备集团"],
    "stage_id": [4, "需求确认"],
}


class FakeResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


def settings(**overrides):
    values = {
        "odoo_url": "http://192.168.106.100:8069",
        "odoo_api_key": "test-api-key",
        "odoo_database": "crm_demo",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def capture_handler_response(handler):
    sent = {}
    handler._send = lambda body, content_type, **kwargs: sent.update(
        body=body,
        content_type=content_type,
        status=kwargs.get("status", 200),
    )
    handler.do_GET()
    sent["json"] = json.loads(sent["body"])
    return sent


def test_maps_odoo_opportunity_to_card():
    assert crm_read.map_opportunity(RECORD) == {
        "id": 417,
        "name": "华东客户扫码枪急单跟进",
        "customer_name": "华东办公设备集团",
        "stage_name": "需求确认",
    }


def test_maps_opportunity_without_customer_or_stage():
    record = {**RECORD, "commercial_partner_id": False, "stage_id": False}

    assert crm_read.map_opportunity(record) == {
        "id": 417,
        "name": "华东客户扫码枪急单跟进",
        "customer_name": None,
        "stage_name": None,
    }


def test_maps_direct_company_customer_when_commercial_partner_is_false():
    # Odoo 19 leaves commercial_partner_id false when partner_id IS the company.
    record = {**RECORD, "commercial_partner_id": False,
              "partner_id": [208, "华东办公设备集团"]}

    assert crm_read.map_opportunity(record)["customer_name"] == "华东办公设备集团"


def test_prefers_company_over_contact_customer():
    record = {**RECORD, "partner_id": [209, "陈经理"]}

    assert crm_read.map_opportunity(record)["customer_name"] == "华东办公设备集团"


def test_maps_empty_json2_result():
    assert crm_read.map_opportunities_response([]) == {"opportunities": []}


def test_maps_json2_result_records():
    record_without_customer = {**RECORD, "id": 418, "commercial_partner_id": False}

    assert crm_read.map_opportunities_response([RECORD, record_without_customer]) == {
        "opportunities": [
            {
                "id": 417,
                "name": "华东客户扫码枪急单跟进",
                "customer_name": "华东办公设备集团",
                "stage_name": "需求确认",
            },
            {
                "id": 418,
                "name": "华东客户扫码枪急单跟进",
                "customer_name": None,
                "stage_name": "需求确认",
            },
        ],
    }


def test_list_opportunities_calls_json2_search_read_and_maps_records():
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse([RECORD])

    result = crm_read.list_opportunities(settings(), opener=fake_urlopen)

    request = captured["request"]
    headers = {name.lower(): value for name, value in request.header_items()}
    body = json.loads(request.data)
    assert request.full_url == (
        "http://192.168.106.100:8069/json/2/crm.lead/search_read"
    )
    assert request.method == "POST"
    assert headers["authorization"] == "bearer test-api-key"
    assert headers["content-type"] == "application/json"
    assert headers["x-odoo-database"] == "crm_demo"
    assert body["domain"] == [["type", "=", "opportunity"]]
    assert body["fields"] == ["id", "name", "commercial_partner_id", "partner_id", "stage_id"]
    assert body["limit"] == 50
    assert captured["timeout"] == 10
    assert result == {
        "opportunities": [
            {
                "id": 417,
                "name": "华东客户扫码枪急单跟进",
                "customer_name": "华东办公设备集团",
                "stage_name": "需求确认",
            },
        ],
    }


def test_list_opportunities_requires_url_and_api_key():
    with pytest.raises(crm_read.CrmConfigurationError):
        crm_read.list_opportunities(
            settings(odoo_url="", odoo_api_key=""),
            opener=lambda *_args, **_kwargs: pytest.fail("must not make a request"),
        )


def test_list_opportunities_reports_odoo_http_errors():
    def fail_with_unauthorized(request, timeout):
        raise HTTPError(request.full_url, 401, "Unauthorized", {}, BytesIO(b"{}"))

    with pytest.raises(crm_read.CrmReadError, match="HTTP 401"):
        crm_read.list_opportunities(settings(), opener=fail_with_unauthorized)


def test_list_opportunities_reports_connection_errors():
    def fail_with_timeout(_request, timeout):
        assert timeout == 10
        raise URLError(TimeoutError("timed out"))

    with pytest.raises(crm_read.CrmReadError, match="connect"):
        crm_read.list_opportunities(settings(), opener=fail_with_timeout)


def test_get_crm_opportunities_returns_json(monkeypatch):
    monkeypatch.setattr(
        crm_read,
        "list_opportunities",
        lambda: {"opportunities": []},
    )
    handler = dashboard.Handler.__new__(dashboard.Handler)
    handler.path = "/api/crm/opportunities"

    sent = capture_handler_response(handler)

    assert sent["content_type"] == "application/json"
    assert sent["status"] == 200
    assert sent["json"] == {"opportunities": []}


def test_get_crm_opportunities_returns_read_error(monkeypatch):
    def fail_read():
        message = "Odoo connection timed out."
        raise crm_read.CrmReadError(message)

    monkeypatch.setattr(crm_read, "list_opportunities", fail_read)
    handler = dashboard.Handler.__new__(dashboard.Handler)
    handler.path = "/api/crm/opportunities"

    sent = capture_handler_response(handler)

    assert sent["content_type"] == "application/json"
    assert sent["status"] == 502
    assert sent["json"] == {"error": "Odoo connection timed out."}
