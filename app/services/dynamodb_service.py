import logging
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError
from app.config import Settings, get_settings
from app.models.notification import NotificationItem, NotificationType

logger = logging.getLogger("studium.notifications.dynamodb")


class DynamoDbService:
    """Manages persistence in Amazon DynamoDB for notifications."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        kwargs: Dict[str, Any] = {"region_name": self.settings.aws_region}

        if self.settings.aws_endpoint_url:
            kwargs["endpoint_url"] = self.settings.aws_endpoint_url
        if self.settings.aws_access_key_id and self.settings.aws_secret_access_key:
            kwargs["aws_access_key_id"] = self.settings.aws_access_key_id
            kwargs["aws_secret_access_key"] = self.settings.aws_secret_access_key

        self.dynamodb = boto3.resource("dynamodb", **kwargs)
        self.client = boto3.client("dynamodb", **kwargs)
        self.table_name = self.settings.dynamodb_table_name
        self.table = self.dynamodb.Table(self.table_name)

    def ensure_table_exists(self) -> None:
        """
        Verifies if the DynamoDB table exists; if not, provisions it with On-Demand billing.
        Key Schema:
          - notification_id (HASH / Partition Key)
        Global Secondary Index (UserIdIndex):
          - user_id (HASH)
          - created_at (RANGE)
        """
        try:
            self.client.describe_table(TableName=self.table_name)
            logger.info(f"DynamoDB table '{self.table_name}' is active.")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.info(f"DynamoDB table '{self.table_name}' does not exist. Creating table...")
                table = self.dynamodb.create_table(
                    TableName=self.table_name,
                    KeySchema=[
                        {"AttributeName": "notification_id", "KeyType": "HASH"},
                    ],
                    AttributeDefinitions=[
                        {"AttributeName": "notification_id", "AttributeType": "S"},
                        {"AttributeName": "user_id", "AttributeType": "S"},
                        {"AttributeName": "created_at", "AttributeType": "S"},
                    ],
                    GlobalSecondaryIndexes=[
                        {
                            "IndexName": "UserIdIndex",
                            "KeySchema": [
                                {"AttributeName": "user_id", "KeyType": "HASH"},
                                {"AttributeName": "created_at", "KeyType": "RANGE"},
                            ],
                            "Projection": {"ProjectionType": "ALL"},
                        }
                    ],
                    BillingMode="PAY_PER_REQUEST",
                )
                logger.info(f"Waiting for DynamoDB table '{self.table_name}' to become active...")
                table.wait_until_exists()
                logger.info(f"DynamoDB table '{self.table_name}' created successfully.")
            else:
                logger.error(f"Error checking DynamoDB table '{self.table_name}': {e}")
                raise

    def save_notification(self, item: NotificationItem) -> Dict[str, Any]:
        """Saves a notification to DynamoDB."""
        doc = {
            "notification_id": item.notification_id,
            "user_id": item.user_id,
            "type": item.type.value,
            "title": item.title,
            "message": item.message,
            "data": item.data,
            "is_read": item.is_read,
            "created_at": item.created_at,
        }
        self.table.put_item(Item=doc)
        logger.info(f"Notification '{item.notification_id}' saved for user '{item.user_id}'.")
        return doc

    def get_user_notifications(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieves recent notifications for a user using UserIdIndex (newest first).
        Also includes broadcast announcements.
        """
        results: List[Dict[str, Any]] = []

        try:
            # Query specific user notifications
            response = self.table.query(
                IndexName="UserIdIndex",
                KeyConditionExpression="user_id = :uid",
                ExpressionAttributeValues={":uid": user_id},
                ScanIndexForward=False,  # Descending order (newest first)
                Limit=limit,
            )
            results.extend(response.get("Items", []))

            # If not requesting broadcast itself, query broadcast alerts as well
            if user_id != "broadcast":
                broadcast_resp = self.table.query(
                    IndexName="UserIdIndex",
                    KeyConditionExpression="user_id = :bcast",
                    ExpressionAttributeValues={":bcast": "broadcast"},
                    ScanIndexForward=False,
                    Limit=10,
                )
                results.extend(broadcast_resp.get("Items", []))

            # Sort merged results by created_at descending
            results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return results[:limit]
        except Exception as e:
            logger.error(f"Error querying notifications for user '{user_id}': {e}")
            raise

    def get_notification(self, notification_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single notification by its primary key."""
        try:
            response = self.table.get_item(Key={"notification_id": notification_id})
            return response.get("Item")
        except Exception as e:
            logger.error(f"Error fetching notification '{notification_id}': {e}")
            raise

    def mark_as_read(self, notification_id: str) -> bool:
        """Marks a notification as read."""
        try:
            self.table.update_item(
                Key={"notification_id": notification_id},
                UpdateExpression="SET is_read = :val",
                ExpressionAttributeValues={":val": True},
            )
            logger.info(f"Notification '{notification_id}' marked as read.")
            return True
        except Exception as e:
            logger.error(f"Error marking notification '{notification_id}' as read: {e}")
            raise

    def ping(self) -> bool:
        """Lightweight connectivity check for health probes."""
        try:
            self.client.describe_table(TableName=self.table_name)
            return True
        except Exception as e:
            logger.warning(f"DynamoDB ping failed: {e}")
            return False
