from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NotificationType(str, Enum):
    RESERVATION_CREATED = "RESERVATION_CREATED"
    RESERVATION_CHECKED_IN = "RESERVATION_CHECKED_IN"
    RESERVATION_CANCELLED = "RESERVATION_CANCELLED"
    NO_SHOW_RECORDED = "NO_SHOW_RECORDED"
    WAITLIST_SLOT_AVAILABLE = "WAITLIST_SLOT_AVAILABLE"
    ROOM_MAINTENANCE_SCHEDULED = "ROOM_MAINTENANCE_SCHEDULED"
    ROOM_MAINTENANCE_CANCELLED = "ROOM_MAINTENANCE_CANCELLED"
    SYSTEM_ALERT = "SYSTEM_ALERT"


class NotificationItem(BaseModel):
    notification_id: str
    user_id: str
    type: NotificationType
    title: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)
    is_read: bool = False
    created_at: str


class NotificationResponse(BaseModel):
    notification_id: str
    user_id: str
    type: NotificationType
    title: str
    message: str
    data: Dict[str, Any]
    is_read: bool
    created_at: str


class NotificationListResponse(BaseModel):
    user_id: str
    total_count: int
    unread_count: int
    items: List[NotificationResponse]


class MarkAsReadResponse(BaseModel):
    notification_id: str
    is_read: bool
    message: str


class CreateNotificationRequest(BaseModel):
    user_id: str = Field(..., alias="userId")
    type: NotificationType = NotificationType.SYSTEM_ALERT
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None

    model_config = {
        "populate_by_name": True
    }


class CreateTestNotificationRequest(BaseModel):
    user_id: str
    type: NotificationType = NotificationType.SYSTEM_ALERT
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
