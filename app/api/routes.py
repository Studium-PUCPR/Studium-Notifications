import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.notification import (
    CreateNotificationRequest,
    CreateTestNotificationRequest,
    MarkAsReadResponse,
    NotificationItem,
    NotificationListResponse,
    NotificationResponse,
    NotificationType,
)
from app.services.dynamodb_service import DynamoDbService

logger = logging.getLogger("studium.notifications.api")

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


def get_dynamo_service() -> DynamoDbService:
    return DynamoDbService()


@router.get("", response_model=NotificationListResponse)
def get_user_notifications(
    user_id: str = Query(..., description="ID of the user (Cognito username/sub)"),
    limit: int = Query(50, ge=1, le=100, description="Max notifications to retrieve"),
    dynamo: DynamoDbService = Depends(get_dynamo_service),
) -> NotificationListResponse:
    """
    Retrieves the in-app notification feed for a user, sorted newest first (UC018).
    Includes direct user alerts and institutional broadcast announcements.
    """
    try:
        items_raw = dynamo.get_user_notifications(user_id=user_id, limit=limit)
        items: list[NotificationResponse] = []
        unread_count = 0

        for row in items_raw:
            is_read = bool(row.get("is_read", False))
            if not is_read:
                unread_count += 1

            items.append(
                NotificationResponse(
                    notification_id=row["notification_id"],
                    user_id=row["user_id"],
                    type=NotificationType(row.get("type", NotificationType.SYSTEM_ALERT.value)),
                    title=row.get("title", ""),
                    message=row.get("message", ""),
                    data=row.get("data", {}),
                    is_read=is_read,
                    created_at=row.get("created_at", ""),
                )
            )

        return NotificationListResponse(
            user_id=user_id,
            total_count=len(items),
            unread_count=unread_count,
            items=items,
        )
    except Exception as e:
        logger.error(f"Error fetching notifications for {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch notifications: {str(e)}",
        )


@router.get("/{notification_id}", response_model=NotificationResponse)
def get_notification_by_id(
    notification_id: str,
    dynamo: DynamoDbService = Depends(get_dynamo_service),
) -> NotificationResponse:
    """Retrieves a single notification by its ID."""
    item = dynamo.get_notification(notification_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found.",
        )

    return NotificationResponse(
        notification_id=item["notification_id"],
        user_id=item["user_id"],
        type=NotificationType(item.get("type", NotificationType.SYSTEM_ALERT.value)),
        title=item.get("title", ""),
        message=item.get("message", ""),
        data=item.get("data", {}),
        is_read=bool(item.get("is_read", False)),
        created_at=item.get("created_at", ""),
    )


@router.patch("/{notification_id}/read", response_model=MarkAsReadResponse)
def mark_notification_as_read(
    notification_id: str,
    dynamo: DynamoDbService = Depends(get_dynamo_service),
) -> MarkAsReadResponse:
    """Marks a notification as read (UC018)."""
    item = dynamo.get_notification(notification_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found.",
        )

    dynamo.mark_as_read(notification_id)
    return MarkAsReadResponse(
        notification_id=notification_id,
        is_read=True,
        message="Notification marked as read successfully.",
    )


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def create_notification(
    request: CreateNotificationRequest,
    dynamo: DynamoDbService = Depends(get_dynamo_service),
) -> NotificationResponse:
    """Dispatches and persists a new notification synchronously."""
    item = NotificationItem(
        notification_id=str(uuid.uuid4()),
        user_id=request.user_id,
        type=request.type,
        title=request.title,
        message=request.message,
        data=request.data or {},
        is_read=False,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    saved = dynamo.save_notification(item)
    return NotificationResponse(
        notification_id=saved["notification_id"],
        user_id=saved["user_id"],
        type=NotificationType(saved["type"]),
        title=saved["title"],
        message=saved["message"],
        data=saved["data"],
        is_read=saved["is_read"],
        created_at=saved["created_at"],
    )


@router.post("/test", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def create_test_notification(
    request: CreateTestNotificationRequest,
    dynamo: DynamoDbService = Depends(get_dynamo_service),
) -> NotificationResponse:
    """
    Manually creates a notification directly in DynamoDB.
    Useful for demonstration, manual verification, and integration tests.
    """
    item = NotificationItem(
        notification_id=str(uuid.uuid4()),
        user_id=request.user_id,
        type=request.type,
        title=request.title,
        message=request.message,
        data=request.data or {},
        is_read=False,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    saved = dynamo.save_notification(item)
    return NotificationResponse(
        notification_id=saved["notification_id"],
        user_id=saved["user_id"],
        type=NotificationType(saved["type"]),
        title=saved["title"],
        message=saved["message"],
        data=saved["data"],
        is_read=saved["is_read"],
        created_at=saved["created_at"],
    )
