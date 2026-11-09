# Studium-Notifications

Stack: `Python 3.12` + `FastAPI` + `Amazon DynamoDB` (`studium_notifications`) + `Amazon SQS` (`boto3`) + `Amazon SES` simulation.

## Rubric R1, R2 & R3 Anchors
* **Technological Diversity (R1):** Introduces **Python** as the second distinct programming language in the platform (complementing C# / .NET 10) and **Amazon DynamoDB** as the second distinct DBMS (NoSQL Key-Value / Document store complementing PostgreSQL).
* **Database per Service (R1):** Isolated persistence on a dedicated DynamoDB table (`studium_notifications`) with On-Demand capacity and a Global Secondary Index (`UserIdIndex`).
* **Containerization & EKS (R2):** Packaged via multi-stage Python 3.12-slim Dockerfile, running under the `studium` namespace on Amazon EKS with health probes and ClusterIP Service (`studium-notifications-service:80`).
* **Asynchronous Messaging & Interoperability (R3):** Asynchronously consumes messages from `studium-notifications-queue`. Features a specialized **Wolverine C# Binary Envelope Unpacker** that decodes JasperFx .NET binary envelopes (Base64 + 7-bit length encoded headers + UTF-8 JSON payloads) as well as raw JSON and CloudEvents.

## Scope & Capabilities
- **In-App Notification Feed (UC018):** Chronological, user-specific feed of operational alerts (reservations, cancellations, waitlist openings, and no-show infractions) under `/api/notifications?user_id={id}`.
- **Read Status Tracking:** Mark notifications as read under `PATCH /api/notifications/{id}/read`.
- **Institutional Broadcasts:** Room maintenance notices broadcasted from `Studium-Catalog` are automatically surfaced in student feeds.
- **Simulated SES Email Alerts:** Dispatches email notifications (or structured logs) on critical reservation milestones and infractions.
- **Test / Demonstration Endpoint:** `POST /api/notifications/test` allows manual trigger for classroom presentation and testing without waiting for an asynchronous event.

## Handled SQS Event Contracts
1. **`ReservationNotificationEvent`** (`studium.booking.reservation-notification`):
   - `ReservationCreated`: Booking confirmed.
   - `ReservationCheckedIn`: Attendance verified.
   - `ReservationCancelled`: Reservation released.
   - `NoShowRecorded`: Attendance grace window expired (15m timer), alerting user about the 5 no-shows in 30 days suspension limit.
2. **`WaitlistSlotAvailableEvent`** (`studium.booking.waitlist-slot-available`):
   - Alerts students that a spot opened up in a previously fully-booked room.
3. **`RoomMaintenanceEvent`** (`studium.catalog.room-maintenance`):
   - Scheduled / cancelled room maintenance alerts.

## Local Setup & Testing

### 1. Create Virtualenv & Install Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Unit Tests
```bash
PYTHONPATH=. pytest tests/ -v
```

### 3. Run Application Locally
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```
Interactive API documentation is accessible at `http://localhost:8080/docs`.
