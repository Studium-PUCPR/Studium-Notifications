try:
    import pytest
except ImportError:
    pytest = None
from app.consumer.handlers import (
    handle_reservation_notification,
    handle_room_maintenance,
    handle_waitlist_slot_available,
    route_event_to_notification,
)
from app.models.notification import NotificationType


def test_handle_reservation_created():
    payload = {
        "eventType": "ReservationCreated",
        "bookingId": "b1",
        "userId": "user-123",
        "roomId": "r1",
        "startsAtUtc": "2026-11-10T14:00:00Z",
        "endsAtUtc": "2026-11-10T16:00:00Z",
        "occurredAtUtc": "2026-11-08T20:00:00Z",
    }
    notif = handle_reservation_notification(payload, {})

    assert notif.user_id == "user-123"
    assert notif.type == NotificationType.RESERVATION_CREATED
    assert "Confirmada" in notif.title
    assert notif.is_read is False


def test_handle_reservation_no_show():
    payload = {
        "eventType": "NoShowRecorded",
        "bookingId": "b2",
        "userId": "user-456",
        "roomId": "r2",
        "startsAtUtc": "2026-11-10T14:00:00Z",
        "endsAtUtc": "2026-11-10T16:00:00Z",
        "occurredAtUtc": "2026-11-10T14:15:00Z",
    }
    notif = handle_reservation_notification(payload, {})

    assert notif.user_id == "user-456"
    assert notif.type == NotificationType.NO_SHOW_RECORDED
    assert "No-Show" in notif.title
    assert "15 minutos" in notif.message


def test_handle_waitlist_slot_available():
    payload = {
        "roomId": "room-abc",
        "waitlistEntryId": "w1",
        "userId": "user-waitlist",
        "startsAtUtc": "2026-11-11T10:00:00Z",
        "endsAtUtc": "2026-11-11T12:00:00Z",
        "occurredAtUtc": "2026-11-08T20:00:00Z",
    }
    notif = handle_waitlist_slot_available(payload, {})

    assert notif.user_id == "user-waitlist"
    assert notif.type == NotificationType.WAITLIST_SLOT_AVAILABLE
    assert "Vaga Liberada" in notif.title


def test_handle_room_maintenance():
    payload = {
        "eventType": 0,  # Scheduled
        "roomId": "r-maint",
        "roomCode": "LAB-101",
        "roomName": "Laboratório de Robótica",
        "reason": "Calibração dos braços mecânicos",
        "startsAtUtc": "2026-11-12T08:00:00Z",
        "endsAtUtc": "2026-11-12T18:00:00Z",
        "occurredAtUtc": "2026-11-08T20:00:00Z",
    }
    notif = handle_room_maintenance(payload, {})

    assert notif.user_id == "broadcast"
    assert notif.type == NotificationType.ROOM_MAINTENANCE_SCHEDULED
    assert "Laboratório de Robótica" in notif.title
    assert "Calibração" in notif.message


def test_route_event_to_notification():
    payload = {"eventType": "ReservationCancelled", "userId": "user-cancel"}
    notif = route_event_to_notification(
        "studium.booking.reservation-notification", payload, {}
    )

    assert notif is not None
    assert notif.type == NotificationType.RESERVATION_CANCELLED
    assert notif.user_id == "user-cancel"
