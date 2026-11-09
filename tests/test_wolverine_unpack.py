import base64
import json
import struct

try:
    import pytest
except ImportError:
    pytest = None
from app.consumer.wolverine_unpack import (
    read_7bit_encoded_int,
    unpack_sqs_message,
    unpack_wolverine_envelope_bytes,
)


def create_mock_wolverine_base64_envelope(
    message_type: str,
    payload_dict: dict,
    correlation_id: str = "corr-123",
) -> str:
    """Helper to assemble a binary Wolverine envelope matching Wolverine's EnvelopeSerializer."""
    payload_bytes = json.dumps(payload_dict).encode("utf-8")

    headers = {
        "message-type": message_type,
        "correlation-id": correlation_id,
        "accepted-content-types": "application/json",
        "id": "msg-guid-456",
    }

    # Encode header entries
    header_bytes = bytearray()
    for k, v in headers.items():
        k_b = k.encode("utf-8")
        header_bytes.append(len(k_b))
        header_bytes.extend(k_b)

        v_b = v.encode("utf-8")
        header_bytes.append(len(v_b))
        header_bytes.extend(v_b)

    buf = bytearray()
    # 8 bytes magic
    buf.extend(b"\x9e\xc5\x5c\xc8\xfc\x3d\xdf\x48")
    # 4 bytes int32 header count
    buf.extend(struct.pack("<i", len(headers)))
    # header bytes
    buf.extend(header_bytes)
    # 4 bytes int32 payload length
    buf.extend(struct.pack("<i", len(payload_bytes)))
    # payload
    buf.extend(payload_bytes)

    return base64.b64encode(buf).decode("utf-8")


def test_unpack_wolverine_base64_envelope():
    payload = {"bookingId": "abc-123", "userId": "student-1", "eventType": "ReservationCreated"}
    base64_msg = create_mock_wolverine_base64_envelope(
        message_type="studium.booking.reservation-notification",
        payload_dict=payload,
    )

    msg_type, headers, extracted_payload = unpack_sqs_message(base64_msg)

    assert msg_type == "studium.booking.reservation-notification"
    assert headers["message-type"] == "studium.booking.reservation-notification"
    assert headers["correlation-id"] == "corr-123"
    assert extracted_payload["bookingId"] == "abc-123"
    assert extracted_payload["userId"] == "student-1"
    assert extracted_payload["eventType"] == "ReservationCreated"


def test_unpack_direct_json_body():
    direct_json = json.dumps(
        {
            "messageType": "studium.booking.waitlist-slot-available",
            "userId": "student-2",
            "roomId": "room-101",
        }
    )

    msg_type, headers, extracted_payload = unpack_sqs_message(direct_json)

    assert msg_type == "studium.booking.waitlist-slot-available"
    assert extracted_payload["userId"] == "student-2"
    assert extracted_payload["roomId"] == "room-101"


def test_unpack_sns_wrapped_json():
    inner_payload = {"eventType": "ReservationCancelled", "userId": "student-3"}
    sns_wrapper = json.dumps(
        {
            "Type": "Notification",
            "Message": json.dumps(inner_payload),
            "MessageAttributes": {
                "message-type": {
                    "Type": "String",
                    "Value": "studium.booking.reservation-notification",
                }
            },
        }
    )

    msg_type, headers, extracted_payload = unpack_sqs_message(sns_wrapper)

    assert extracted_payload["eventType"] == "ReservationCancelled"
    assert extracted_payload["userId"] == "student-3"
