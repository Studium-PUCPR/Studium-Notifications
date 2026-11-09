import base64
import json
import logging
import struct
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("studium.notifications.unpack")


def read_7bit_encoded_int(data: bytes, pos: int) -> Tuple[int, int]:
    """Reads a .NET 7-bit encoded integer used by BinaryReader.ReadString()."""
    count = 0
    shift = 0
    while True:
        if pos >= len(data):
            raise ValueError("Unexpected end of data while reading 7-bit encoded int")
        b = data[pos]
        pos += 1
        count |= (b & 0x7F) << shift
        shift += 7
        if (b & 0x80) == 0:
            break
    return count, pos


def unpack_wolverine_envelope_bytes(raw_bytes: bytes) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
    """
    Unpacks a raw binary Wolverine Envelope created by Wolverine's EnvelopeSerializer.
    Format:
      - 8 bytes: header identifier / timestamp
      - 4 bytes: header count (int32, little-endian)
      - For each header:
          - key: 7-bit encoded length + UTF-8 string
          - value: 7-bit encoded length + UTF-8 string
      - 4 bytes: payload length (int32, little-endian)
      - payload: UTF-8 JSON bytes
    """
    if len(raw_bytes) < 12:
        raise ValueError(f"Wolverine binary envelope too short ({len(raw_bytes)} bytes)")

    offset = 8  # Skip initial 8 magic bytes

    header_count = struct.unpack_from("<i", raw_bytes, offset)[0]
    offset += 4

    headers: Dict[str, str] = {}
    for _ in range(header_count):
        k_len, offset = read_7bit_encoded_int(raw_bytes, offset)
        key = raw_bytes[offset : offset + k_len].decode("utf-8")
        offset += k_len

        v_len, offset = read_7bit_encoded_int(raw_bytes, offset)
        val = raw_bytes[offset : offset + v_len].decode("utf-8")
        offset += v_len
        headers[key] = val

    if offset + 4 > len(raw_bytes):
        raise ValueError("Unexpected end of data reading payload length")

    payload_len = struct.unpack_from("<i", raw_bytes, offset)[0]
    offset += 4

    payload_bytes = raw_bytes[offset : offset + payload_len]
    payload_str = payload_bytes.decode("utf-8")
    payload_json = json.loads(payload_str)

    message_type = headers.get("message-type", "")
    return message_type, headers, payload_json


def unpack_sqs_message(
    body: str,
    message_attributes: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
    """
    Extracts (message_type, headers, payload_dict) from an SQS message.
    Supports:
      1. Base64 Wolverine Envelope (standard DefaultSqsEnvelopeMapper wire format).
      2. Direct JSON body (Raw JSON or CloudEvents).
      3. Wrapped SNS payload containing a Wolverine base64 or JSON message.
    """
    message_attributes = message_attributes or {}
    headers: Dict[str, str] = {}

    # Extract any top-level SQS message attributes
    for k, v in message_attributes.items():
        if isinstance(v, dict) and "StringValue" in v:
            headers[k] = v["StringValue"]
        elif isinstance(v, str):
            headers[k] = v

    # Check if the body itself is a JSON object
    trimmed_body = body.strip()
    if trimmed_body.startswith("{") and trimmed_body.endswith("}"):
        try:
            parsed_json = json.loads(trimmed_body)

            # Check if this is an SNS notification wrapping the message
            if "Type" in parsed_json and parsed_json.get("Type") == "Notification" and "Message" in parsed_json:
                inner_body = parsed_json["Message"]
                return unpack_sqs_message(inner_body, message_attributes)

            # Check if this is CloudEvents JSON
            if "type" in parsed_json and "data" in parsed_json:
                msg_type = parsed_json["type"]
                return msg_type, headers, parsed_json["data"]

            # Direct JSON payload
            msg_type = (
                headers.get("message-type")
                or parsed_json.get("messageType")
                or parsed_json.get("eventType")
                or parsed_json.get("$type")
                or ""
            )
            return msg_type, headers, parsed_json
        except Exception as e:
            logger.debug(f"JSON parse attempt failed, falling back to base64 unpack: {e}")

    # Attempt Base64 decoding (standard Wolverine DefaultSqsEnvelopeMapper)
    try:
        raw_bytes = base64.b64decode(trimmed_body)
        msg_type, env_headers, payload = unpack_wolverine_envelope_bytes(raw_bytes)
        # Merge headers (envelope headers take precedence)
        merged_headers = {**headers, **env_headers}
        return msg_type, merged_headers, payload
    except Exception as e:
        logger.error(f"Failed to unpack message body as Wolverine envelope: {e}")
        raise ValueError(f"Could not unpack message body as JSON or Wolverine envelope: {e}") from e


def unpack_rabbitmq_message(
    body_bytes: bytes, amqp_headers: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
    """
    Extracts (message_type, headers, payload_dict) from a RabbitMQ AMQP message.
    Supports:
      1. Binary Wolverine Envelope (starts with 8-byte header identifier).
      2. UTF-8 JSON body.
      3. Base64 encoded Wolverine envelope.
    """
    headers: Dict[str, str] = {}
    if amqp_headers:
        for k, v in amqp_headers.items():
            headers[str(k)] = str(v)

    # 1. Try unpacking as raw Wolverine binary envelope
    if len(body_bytes) >= 12:
        try:
            msg_type, env_headers, payload = unpack_wolverine_envelope_bytes(body_bytes)
            merged_headers = {**headers, **env_headers}
            return msg_type, merged_headers, payload
        except Exception:
            pass

    # 2. Try UTF-8 decode
    text = ""
    try:
        text = body_bytes.decode("utf-8").strip()
    except Exception:
        pass

    if text:
        # Check if direct JSON
        if text.startswith("{") and text.endswith("}"):
            try:
                parsed_json = json.loads(text)
                msg_type = (
                    headers.get("message-type")
                    or parsed_json.get("type")
                    or parsed_json.get("messageType")
                    or parsed_json.get("eventType")
                    or parsed_json.get("$type")
                    or ""
                )
                payload = parsed_json.get("data", parsed_json)
                return msg_type, headers, payload
            except Exception:
                pass

        # Try base64
        try:
            raw_bytes = base64.b64decode(text)
            msg_type, env_headers, payload = unpack_wolverine_envelope_bytes(raw_bytes)
            return msg_type, {**headers, **env_headers}, payload
        except Exception:
            pass

    raise ValueError(f"Could not unpack RabbitMQ message ({len(body_bytes)} bytes)")
