from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pytest
from fastapi.testclient import TestClient
from app.api.routes import get_dynamo_service
from app.main import app
from app.models.notification import NotificationItem, NotificationType


class InMemoryDynamoDbService:
    """In-memory mock for DynamoDbService in testing."""

    def __init__(self):
        self.items: Dict[str, Dict[str, Any]] = {}

    def ensure_table_exists(self) -> None:
        pass

    def save_notification(self, item: NotificationItem) -> Dict[str, Any]:
        now_epoch = int(datetime.now(timezone.utc).timestamp())
        ttl_epoch = item.ttl if item.ttl is not None else now_epoch + (3 * 24 * 60 * 60)
        doc = {
            "notification_id": item.notification_id,
            "user_id": item.user_id,
            "type": item.type.value,
            "title": item.title,
            "message": item.message,
            "data": item.data,
            "is_read": item.is_read,
            "created_at": item.created_at,
            "ttl": ttl_epoch,
        }
        self.items[item.notification_id] = doc
        return doc

    def get_user_notifications(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        results = [
            doc
            for doc in self.items.values()
            if doc["user_id"] == user_id or doc["user_id"] == "broadcast"
        ]
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results[:limit]

    def get_notification(self, notification_id: str) -> Optional[Dict[str, Any]]:
        return self.items.get(notification_id)

    def mark_as_read(self, notification_id: str) -> bool:
        if notification_id in self.items:
            self.items[notification_id]["is_read"] = True
            return True
        return False

    def ping(self) -> bool:
        return True


mock_db = InMemoryDynamoDbService()
app.dependency_overrides[get_dynamo_service] = lambda: mock_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_mock_db():
    mock_db.items.clear()


def test_health_endpoints():
    # Shallow liveness
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Studium-Notifications"
    assert data["status"] == "Healthy"

    # Deep readiness
    ready_resp = client.get("/health/ready")
    assert ready_resp.status_code == 200
    ready_data = ready_resp.json()
    assert ready_data["dynamodb"] == "Connected"


def test_create_and_get_notifications():
    # 1. Create a test notification
    create_payload = {
        "user_id": "test-student-1",
        "type": "RESERVATION_CREATED",
        "title": "Nova Reserva",
        "message": "Sua sala foi agendada com sucesso.",
        "data": {"room": "Auditório"},
    }
    create_resp = client.post("/api/notifications/test", json=create_payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    notif_id = created_data["notification_id"]
    assert created_data["is_read"] is False
    assert created_data["ttl"] is not None
    assert created_data["ttl"] > int(datetime.now(timezone.utc).timestamp())

    # 2. Query user notifications
    get_resp = client.get("/api/notifications", params={"user_id": "test-student-1"})
    assert get_resp.status_code == 200
    feed = get_resp.json()
    assert feed["user_id"] == "test-student-1"
    assert feed["total_count"] == 1
    assert feed["unread_count"] == 1
    assert feed["items"][0]["notification_id"] == notif_id
    assert feed["items"][0]["ttl"] == created_data["ttl"]

    # 3. Mark notification as read
    patch_resp = client.patch(f"/api/notifications/{notif_id}/read")
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_read"] is True

    # 4. Query again and verify unread count is now 0
    get_resp_after = client.get("/api/notifications", params={"user_id": "test-student-1"})
    assert get_resp_after.json()["unread_count"] == 0


def test_create_notification_canonical():
    payload = {
        "userId": "user-456",
        "type": "NO_SHOW_RECORDED",
        "title": "Prazo de Confirmação Expirado",
        "message": "Você não confirmou a presença na reserva a tempo.",
        "data": {"bookingId": "b-123"}
    }
    resp = client.post("/api/notifications", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_id"] == "user-456"
    assert body["type"] == "NO_SHOW_RECORDED"
    assert body["title"] == "Prazo de Confirmação Expirado"
    assert body["is_read"] is False
