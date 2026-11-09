import asyncio
import logging
from typing import Any, Dict, Optional
import boto3
from botocore.exceptions import ClientError
from app.config import Settings, get_settings
from app.consumer.handlers import route_event_to_notification
from app.consumer.wolverine_unpack import unpack_sqs_message
from app.services.dynamodb_service import DynamoDbService
from app.services.email_service import EmailService

logger = logging.getLogger("studium.notifications.worker")


class SqsNotificationWorker:
    """Background worker that continuously polls and processes studium-notifications-queue."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        dynamo_service: Optional[DynamoDbService] = None,
        email_service: Optional[EmailService] = None,
    ):
        self.settings = settings or get_settings()
        self.dynamo = dynamo_service or DynamoDbService(self.settings)
        self.email = email_service or EmailService(self.settings)

        kwargs: Dict[str, Any] = {"region_name": self.settings.aws_region}
        if self.settings.aws_endpoint_url:
            kwargs["endpoint_url"] = self.settings.aws_endpoint_url
        if self.settings.aws_access_key_id and self.settings.aws_secret_access_key:
            kwargs["aws_access_key_id"] = self.settings.aws_access_key_id
            kwargs["aws_secret_access_key"] = self.settings.aws_secret_access_key

        self.sqs = boto3.client("sqs", **kwargs)
        self.queue_url: Optional[str] = self.settings.aws_sqs_queue_url
        self.running = False
        self._task: Optional[asyncio.Task] = None

    def _resolve_queue_url(self) -> str:
        """Resolves the SQS Queue URL from the queue name if not already set."""
        if self.queue_url:
            return self.queue_url

        queue_name = self.settings.aws_sqs_notifications_queue_name
        try:
            resp = self.sqs.get_queue_url(QueueName=queue_name)
            self.queue_url = resp["QueueUrl"]
            logger.info(f"Resolved SQS queue URL for '{queue_name}': {self.queue_url}")
            return self.queue_url
        except ClientError as e:
            logger.warning(
                f"Could not resolve SQS queue '{queue_name}' yet: {e}. Worker will retry."
            )
            raise

    async def start(self) -> None:
        """Starts the background listening loop."""
        self.running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("SQS Notification Worker started.")

    async def stop(self) -> None:
        """Gracefully stops the worker."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SQS Notification Worker stopped.")

    async def _poll_loop(self) -> None:
        """Main polling loop running on an asyncio thread executor."""
        loop = asyncio.get_running_loop()

        while self.running:
            try:
                # Ensure queue URL is resolved
                if not self.queue_url:
                    try:
                        await loop.run_in_executor(None, self._resolve_queue_url)
                    except Exception:
                        await asyncio.sleep(5)
                        continue

                # Poll messages in executor
                messages = await loop.run_in_executor(None, self._receive_messages)

                for msg in messages:
                    if not self.running:
                        break
                    await loop.run_in_executor(None, self._process_single_message, msg)

                await asyncio.sleep(self.settings.sqs_poll_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in SQS poll loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    def _receive_messages(self) -> list:
        """Synchronous boto3 receive_message call."""
        if not self.queue_url:
            return []
        try:
            resp = self.sqs.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=self.settings.sqs_max_messages,
                WaitTimeSeconds=self.settings.sqs_wait_time_seconds,
                AttributeNames=["All"],
                MessageAttributeNames=["All"],
            )
            return resp.get("Messages", [])
        except ClientError as e:
            logger.warning(f"Error receiving messages from SQS: {e}")
            return []

    def _process_single_message(self, message: Dict[str, Any]) -> None:
        """Unpacks Wolverine message, routes to handler, saves to DynamoDB, and deletes from SQS."""
        receipt_handle = message.get("ReceiptHandle")
        body = message.get("Body", "")
        message_attributes = message.get("MessageAttributes", {})

        try:
            # Unpack Wolverine Base64 Envelope or JSON
            msg_type, headers, payload = unpack_sqs_message(body, message_attributes)
            logger.info(f"Processing SQS message of type '{msg_type}'.")

            # Route to business notification item
            notification = route_event_to_notification(msg_type, payload, headers)

            if notification:
                # Persist in DynamoDB
                self.dynamo.save_notification(notification)

                # Dispatch Email Alert
                self.email.send_notification_email(notification)

            # Acknowledge & delete from SQS
            if self.queue_url and receipt_handle:
                self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt_handle)
                logger.info(f"Message '{message.get('MessageId')}' acknowledged and deleted from SQS.")

        except Exception as e:
            logger.error(f"Failed to process message {message.get('MessageId')}: {e}", exc_info=True)
            # Message will remain in SQS and reappear after visibility timeout or move to DLQ
