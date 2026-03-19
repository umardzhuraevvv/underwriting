"""Тесты webhook-уведомлений: CRUD, подпись HMAC, отправка при conclude."""

import hashlib
import hmac
import json
from unittest.mock import patch, MagicMock

import pytest

from app.database import WebhookConfig, Anketa
from app.services.webhook_service import _sign_payload, _build_payload, send_webhook, notify_webhooks


# ===== CRUD API =====

class TestWebhookCRUD:
    def test_create_webhook(self, client, admin_headers, seeded_db):
        resp = client.post("/api/v1/admin/webhooks", json={
            "name": "Партнёр X",
            "url": "https://partner.example.com/webhook",
            "secret": "my_secret_key",
            "events": "approved,rejected",
        }, headers=admin_headers)
        assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["name"] == "Партнёр X"
        assert data["url"] == "https://partner.example.com/webhook"
        assert data["secret"] == "my_secret_key"
        assert data["events"] == "approved,rejected"
        assert data["is_active"] is True
        assert data["id"] is not None

    def test_list_webhooks(self, client, admin_headers, seeded_db):
        # Создать два webhook-конфига
        client.post("/api/v1/admin/webhooks", json={
            "name": "Hook 1", "url": "https://hook1.example.com/wh",
        }, headers=admin_headers)
        client.post("/api/v1/admin/webhooks", json={
            "name": "Hook 2", "url": "https://hook2.example.com/wh",
        }, headers=admin_headers)

        resp = client.get("/api/v1/admin/webhooks", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = {w["name"] for w in data}
        assert names == {"Hook 1", "Hook 2"}

    def test_update_webhook(self, client, admin_headers, seeded_db):
        create_resp = client.post("/api/v1/admin/webhooks", json={
            "name": "Test", "url": "https://test.example.com/wh",
        }, headers=admin_headers)
        wh_id = create_resp.json()["id"]

        resp = client.patch(f"/api/v1/admin/webhooks/{wh_id}", json={
            "name": "Updated",
            "url": "https://updated.example.com/wh",
            "is_active": False,
        }, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated"
        assert data["url"] == "https://updated.example.com/wh"
        assert data["is_active"] is False

    def test_delete_webhook(self, client, admin_headers, seeded_db):
        create_resp = client.post("/api/v1/admin/webhooks", json={
            "name": "ToDelete", "url": "https://del.example.com/wh",
        }, headers=admin_headers)
        wh_id = create_resp.json()["id"]

        resp = client.delete(f"/api/v1/admin/webhooks/{wh_id}", headers=admin_headers)
        assert resp.status_code == 200

        list_resp = client.get("/api/v1/admin/webhooks", headers=admin_headers)
        assert len(list_resp.json()) == 0

    def test_webhook_requires_rules_manage(self, client, inspector_headers, seeded_db):
        resp = client.get("/api/v1/admin/webhooks", headers=inspector_headers)
        assert resp.status_code == 403

    def test_update_nonexistent_webhook(self, client, admin_headers, seeded_db):
        resp = client.patch("/api/v1/admin/webhooks/9999", json={"name": "X"}, headers=admin_headers)
        assert resp.status_code == 404

    def test_delete_nonexistent_webhook(self, client, admin_headers, seeded_db):
        resp = client.delete("/api/v1/admin/webhooks/9999", headers=admin_headers)
        assert resp.status_code == 404


# ===== HMAC подпись =====

class TestWebhookSignature:
    def test_sign_payload(self):
        body = b'{"event":"test"}'
        secret = "test_secret"
        result = _sign_payload(body, secret)
        expected = "sha256=" + hmac.new(
            secret.encode(), body, hashlib.sha256
        ).hexdigest()
        assert result == expected

    def test_sign_payload_different_secrets(self):
        body = b'{"event":"test"}'
        sig1 = _sign_payload(body, "secret1")
        sig2 = _sign_payload(body, "secret2")
        assert sig1 != sig2

    def test_sign_payload_consistent(self):
        body = b'{"event":"test","id":1}'
        secret = "consistent"
        sig1 = _sign_payload(body, secret)
        sig2 = _sign_payload(body, secret)
        assert sig1 == sig2


# ===== send_webhook =====

class TestSendWebhook:
    @patch("app.services.webhook_service.httpx.Client")
    def test_send_webhook_with_signature(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = MagicMock(status_code=200)
        mock_client_cls.return_value = mock_client

        config = MagicMock()
        config.name = "Test"
        config.url = "https://example.com/wh"
        config.secret = "my_secret"

        payload = {"event": "anketa.approved", "anketa_id": 1}
        send_webhook(config, "anketa.approved", payload)

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert "X-Webhook-Signature" in headers
        assert headers["X-Webhook-Signature"].startswith("sha256=")

    @patch("app.services.webhook_service.httpx.Client")
    def test_send_webhook_without_secret(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = MagicMock(status_code=200)
        mock_client_cls.return_value = mock_client

        config = MagicMock()
        config.name = "Test"
        config.url = "https://example.com/wh"
        config.secret = None

        payload = {"event": "test"}
        send_webhook(config, "test", payload)

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert "X-Webhook-Signature" not in headers


# ===== Webhook при conclude =====

class TestWebhookOnConclude:
    @patch("app.services.webhook_service.httpx.Client")
    def test_webhook_on_conclude(self, mock_client_cls, client, admin_headers, sample_anketa_data, seeded_db):
        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.post.return_value = MagicMock(status_code=200)
        mock_client_cls.return_value = mock_http

        db = seeded_db["session"]
        # Создать webhook-конфиг
        wh = WebhookConfig(
            name="Test Hook", url="https://test.example.com/wh",
            secret="s3cret", events="all", is_active=True,
            created_by=seeded_db["admin"].id,
        )
        db.add(wh)
        db.commit()

        # Создать → заполнить → сохранить → заключить анкету
        create_resp = client.post("/api/v1/anketas?client_type=individual", headers=admin_headers)
        anketa_id = create_resp.json()["id"]
        client.patch(f"/api/v1/anketas/{anketa_id}", json=sample_anketa_data, headers=admin_headers)
        client.post(f"/api/v1/anketas/{anketa_id}/save", headers=admin_headers)

        resp = client.post(
            f"/api/v1/anketas/{anketa_id}/conclude",
            json={"decision": "rejected_underwriter", "comment": "OK", "final_pv": 20},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Conclude → 200, получили {resp.status_code}: {resp.text}"

        # Проверить что httpx.Client().post был вызван (webhook отправлен)
        assert mock_http.post.called, "Webhook должен быть отправлен при conclude"
        call_kwargs = mock_http.post.call_args
        sent_url = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("url")
        assert sent_url == "https://test.example.com/wh"

        # Проверить payload
        sent_body = call_kwargs.kwargs.get("content") or call_kwargs[1].get("content")
        payload = json.loads(sent_body)
        assert payload["event"] == "anketa.rejected_underwriter"
        assert payload["anketa_id"] == anketa_id
        assert payload["decision"] == "rejected_underwriter"

    @patch("app.services.webhook_service.httpx.Client")
    def test_webhook_not_sent_for_filtered_events(self, mock_client_cls, client, admin_headers, sample_anketa_data, seeded_db):
        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.post.return_value = MagicMock(status_code=200)
        mock_client_cls.return_value = mock_http

        db = seeded_db["session"]
        # Webhook слушает только approved (но авто-вердикт rejected — одобрение невозможно)
        wh = WebhookConfig(
            name="Approved Only", url="https://approved.example.com/wh",
            events="approved", is_active=True,
            created_by=seeded_db["admin"].id,
        )
        db.add(wh)
        db.commit()

        create_resp = client.post("/api/v1/anketas?client_type=individual", headers=admin_headers)
        anketa_id = create_resp.json()["id"]
        client.patch(f"/api/v1/anketas/{anketa_id}", json=sample_anketa_data, headers=admin_headers)
        client.post(f"/api/v1/anketas/{anketa_id}/save", headers=admin_headers)

        resp = client.post(
            f"/api/v1/anketas/{anketa_id}/conclude",
            json={"decision": "rejected_underwriter", "comment": "OK", "final_pv": 20},
            headers=admin_headers,
        )
        assert resp.status_code == 200

        # Webhook НЕ должен быть вызван (events=approved, а decision=rejected_underwriter)
        assert not mock_http.post.called, "Webhook не должен отправляться для отфильтрованного события"
