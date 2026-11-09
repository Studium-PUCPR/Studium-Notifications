import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.models.notification import NotificationItem, NotificationType

logger = logging.getLogger("studium.notifications.handlers")


def parse_datetime(dt_val: Any) -> str:
    """Standardizes datetime value into ISO 8601 UTC string."""
    if not dt_val:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(dt_val, str):
        return dt_val
    if isinstance(dt_val, (int, float)):
        return datetime.fromtimestamp(dt_val, tz=timezone.utc).isoformat()
    return str(dt_val)


def handle_reservation_notification(payload: Dict[str, Any], headers: Dict[str, str]) -> NotificationItem:
    """
    Handles 'studium.booking.reservation-notification' events:
    - ReservationCreated
    - ReservationCheckedIn
    - ReservationCancelled
    - NoShowRecorded
    """
    event_type = payload.get("eventType") or payload.get("EventType") or "ReservationCreated"
    user_id = str(payload.get("userId") or payload.get("UserId") or "")
    booking_id = str(payload.get("bookingId") or payload.get("BookingId") or "")
    room_id = str(payload.get("roomId") or payload.get("RoomId") or "")
    starts_at = parse_datetime(payload.get("startsAtUtc") or payload.get("StartsAtUtc"))
    ends_at = parse_datetime(payload.get("endsAtUtc") or payload.get("EndsAtUtc"))
    additional_info = payload.get("additionalInfo") or payload.get("AdditionalInfo")
    occurred_at = parse_datetime(payload.get("occurredAtUtc") or payload.get("OccurredAtUtc"))

    if "Created" in event_type:
        notif_type = NotificationType.RESERVATION_CREATED
        title = "Reserva Confirmada"
        message = f"Sua reserva para a sala foi confirmada para {starts_at}. Não se esqueça de realizar o check-in."
    elif "CheckedIn" in event_type:
        notif_type = NotificationType.RESERVATION_CHECKED_IN
        title = "Check-in Realizado"
        message = "Check-in confirmado com sucesso! Tenha um excelente período de estudos."
    elif "Cancelled" in event_type:
        notif_type = NotificationType.RESERVATION_CANCELLED
        title = "Reserva Cancelada"
        reason_txt = f" Motivo: {additional_info}" if additional_info else ""
        message = f"Sua reserva foi cancelada com sucesso.{reason_txt}"
    elif "NoShow" in event_type:
        notif_type = NotificationType.NO_SHOW_RECORDED
        title = "Alerta de Não Comparecimento (No-Show)"
        message = (
            "Foi registrado que você não compareceu à sua reserva dentro do tempo limite de 15 minutos. "
            "A sala foi liberada. Lembre-se de que 5 no-shows nos últimos 30 dias resultam em bloqueio de conta."
        )
    else:
        notif_type = NotificationType.SYSTEM_ALERT
        title = f"Atualização de Reserva ({event_type})"
        message = f"Houve uma atualização na sua reserva ({booking_id})."

    return NotificationItem(
        notification_id=str(uuid.uuid4()),
        user_id=user_id,
        type=notif_type,
        title=title,
        message=message,
        data={
            "booking_id": booking_id,
            "room_id": room_id,
            "starts_at_utc": starts_at,
            "ends_at_utc": ends_at,
            "event_type": event_type,
            "additional_info": additional_info,
        },
        is_read=False,
        created_at=occurred_at,
    )


def handle_waitlist_slot_available(payload: Dict[str, Any], headers: Dict[str, str]) -> NotificationItem:
    """
    Handles 'studium.booking.waitlist-slot-available' events.
    Notifies a user queued on the waitlist that a slot has freed up.
    """
    user_id = str(payload.get("userId") or payload.get("UserId") or "")
    room_id = str(payload.get("roomId") or payload.get("RoomId") or "")
    waitlist_id = str(payload.get("waitlistEntryId") or payload.get("WaitlistEntryId") or "")
    starts_at = parse_datetime(payload.get("startsAtUtc") or payload.get("StartsAtUtc"))
    ends_at = parse_datetime(payload.get("endsAtUtc") or payload.get("EndsAtUtc"))
    occurred_at = parse_datetime(payload.get("occurredAtUtc") or payload.get("OccurredAtUtc"))

    title = "Vaga Liberada na Fila de Espera!"
    message = (
        f"Uma vaga na sala que você aguardava foi liberada para o horário {starts_at} até {ends_at}. "
        "Acesse o Studium para confirmar sua reserva imediatamente."
    )

    return NotificationItem(
        notification_id=str(uuid.uuid4()),
        user_id=user_id,
        type=NotificationType.WAITLIST_SLOT_AVAILABLE,
        title=title,
        message=message,
        data={
            "room_id": room_id,
            "waitlist_entry_id": waitlist_id,
            "starts_at_utc": starts_at,
            "ends_at_utc": ends_at,
        },
        is_read=False,
        created_at=occurred_at,
    )


def handle_room_maintenance(payload: Dict[str, Any], headers: Dict[str, str]) -> NotificationItem:
    """
    Handles 'studium.catalog.room-maintenance' events.
    Broadcasting room maintenance alerts.
    """
    event_type = payload.get("eventType") or payload.get("EventType")
    # EventType may be int (0 = Scheduled, 1 = Cancelled) or string
    is_cancelled = event_type == 1 or event_type == "MaintenanceCancelled"

    room_name = payload.get("roomName") or payload.get("RoomName") or "Sala"
    room_code = payload.get("roomCode") or payload.get("RoomCode") or ""
    room_id = str(payload.get("roomId") or payload.get("RoomId") or "")
    reason = payload.get("reason") or payload.get("Reason") or "Manutenção periódica"
    starts_at = parse_datetime(payload.get("startsAtUtc") or payload.get("StartsAtUtc"))
    ends_at = parse_datetime(payload.get("endsAtUtc") or payload.get("EndsAtUtc"))
    occurred_at = parse_datetime(payload.get("occurredAtUtc") or payload.get("OccurredAtUtc"))

    if is_cancelled:
        notif_type = NotificationType.ROOM_MAINTENANCE_CANCELLED
        title = f"Manutenção Cancelada: {room_name} ({room_code})"
        message = f"A manutenção previamente agendada para a sala {room_name} foi cancelada. O espaço está novamente operacional."
    else:
        notif_type = NotificationType.ROOM_MAINTENANCE_SCHEDULED
        title = f"Aviso de Manutenção: {room_name} ({room_code})"
        message = f"A sala {room_name} estará em manutenção de {starts_at} até {ends_at}. Motivo: {reason}."

    # Broadcast / institutional alert - mapped to 'all' or institutional feed
    return NotificationItem(
        notification_id=str(uuid.uuid4()),
        user_id="broadcast",
        type=notif_type,
        title=title,
        message=message,
        data={
            "room_id": room_id,
            "room_code": room_code,
            "room_name": room_name,
            "reason": reason,
            "starts_at_utc": starts_at,
            "ends_at_utc": ends_at,
        },
        is_read=False,
        created_at=occurred_at,
    )


def route_event_to_notification(
    message_type: str, payload: Dict[str, Any], headers: Dict[str, str]
) -> Optional[NotificationItem]:
    """
    Dispatches unpacked event to the corresponding notification generator.
    """
    logger.info(f"Routing message type: '{message_type}'")

    if "reservation-notification" in message_type or "ReservationNotificationEvent" in message_type:
        return handle_reservation_notification(payload, headers)
    elif "waitlist-slot-available" in message_type or "WaitlistSlotAvailableEvent" in message_type:
        return handle_waitlist_slot_available(payload, headers)
    elif "room-maintenance" in message_type or "RoomMaintenanceEvent" in message_type:
        return handle_room_maintenance(payload, headers)
    else:
        logger.warning(f"No specific handler for message type '{message_type}'. Creating generic notification.")
        # Check if payload has user and title/message
        user_id = str(payload.get("userId") or payload.get("UserId") or "system")
        return NotificationItem(
            notification_id=str(uuid.uuid4()),
            user_id=user_id,
            type=NotificationType.SYSTEM_ALERT,
            title="Aviso do Sistema Studium",
            message=str(payload.get("message") or payload.get("reason") or "Nova notificação recebida."),
            data=payload,
            is_read=False,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
