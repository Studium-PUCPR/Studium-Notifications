# Studium-Notifications — Project State & Agent Context (`AGENTS.md`)

> **MANDATORY AGENT DIRECTIVE:**
> After **every user prompt**, always evaluate whether we reached a useful architectural conclusion, resolved a design question, or made code/configuration changes. If so, **update both the relevant sections and Section 3 (`Recent Changes History`) in this `./AGENTS.md` file before finishing your turn** so any future chat session immediately has full context of the project state.

---

## 1. Architectural Decisions & Conclusions Log

### 1.1 Python 3.12 & FastAPI for Tech Diversity (Rubric R1 Anchor)
- **Problem Solved:** Rubric R1 mandates that the platform must employ at least **two distinct programming languages** and at least **two distinct DBMSs**. The existing backend services (`Studium-Users`, `Studium-Catalog`, `Studium-Booking`) were implemented in C# (.NET 10) with PostgreSQL.
- **Chosen Solution:** Implemented `Studium-Notifications` using **Python 3.12** and **FastAPI**, providing high-performance asynchronous event processing and a modern REST API.

### 1.2 Amazon DynamoDB as Secondary DBMS (Rubric R1 Anchor)
- **Problem Solved:** Fulfills the requirement for two different DBMS technologies while maintaining the Database-per-Service principle.
- **Chosen Solution:** Amazon DynamoDB (managed NoSQL key-value/document store):
  - Table: `studium_notifications`
  - Partition Key: `notification_id` (String UUID)
  - Global Secondary Index (GSI): `UserIdIndex` with Partition Key `user_id` (String) and Sort Key `created_at` (String ISO 8601 UTC) for instant chronological user feed queries.
  - Billing Mode: `PAY_PER_REQUEST` (On-Demand capacity).

### 1.3 Unpacking Wolverine C# Binary Envelopes in Python
- **Problem Solved:** Upstream services (`Studium-Booking` and `Studium-Catalog`) publish events via `WolverineFx.AmazonSqs` using `DefaultSqsEnvelopeMapper`. Wolverine packages messages into a binary envelope (magic identifier, 4-byte header count, 7-bit length encoded key/value pairs, 4-byte payload length, and UTF-8 JSON payload) and encodes it as Base64 in the SQS message body.
- **Chosen Solution:** Authored `app/consumer/wolverine_unpack.py` with custom deserialization:
  - Supports standard Wolverine binary envelopes (decoding 7-bit length strings for `message-type`, `correlation-id`, `id`).
  - Supports direct JSON / CloudEvents payloads and SNS-wrapped envelopes transparently.

### 1.4 Background Worker & Lifespan Architecture
- Uses FastAPI lifespan context manager (`@asynccontextmanager`) to manage the background `SqsNotificationWorker`.
- Automatically provisions the DynamoDB table if it does not exist on initial startup.
- Long-polls `studium-notifications-queue` with `WaitTimeSeconds=20`, deletes messages upon successful processing, and leaves failed messages for visibility retry or dead-letter queue routing.

---

## 2. Project Structure & File Map
- **`app/`:**
  - `main.py` — Composition root, FastAPI app, CORS, lifespan startup/shutdown, and `/health` probe.
  - `config.py` — Pydantic `BaseSettings` reading environment variables (AWS region, queues, DynamoDB table).
  - `models/notification.py` — Pydantic domain models: `NotificationType`, `NotificationItem`, `NotificationResponse`, `NotificationListResponse`.
  - `consumer/wolverine_unpack.py` — Binary Wolverine C# envelope decoder and JSON fallback parser.
  - `consumer/handlers.py` — Event dispatchers transforming incoming events into localized student notifications.
  - `consumer/worker.py` — Async background polling loop over SQS queue using boto3.
  - `services/dynamodb_service.py` — DynamoDB table management, put_item, query, update_item, and ping.
  - `services/email_service.py` — SES / simulated email dispatcher.
  - `api/routes.py` — REST endpoints (`GET /api/notifications`, `PATCH /api/notifications/{id}/read`, `POST /api/notifications/test`).
- **`tests/`:**
  - `test_wolverine_unpack.py` — Tests decoding Wolverine binary Base64 envelopes, raw JSON, and SNS envelopes.
  - `test_handlers.py` — Tests event mapping (ReservationCreated, NoShowRecorded, WaitlistSlotAvailable, RoomMaintenance).
  - `test_api.py` — FastAPI TestClient testing health probe and notification feed CRUD.
- [`Dockerfile`](./Dockerfile) — Multi-stage production container with Python 3.12-slim and non-root user.
- [`k8s/deployment.yaml`](./k8s/deployment.yaml) — Kubernetes Deployment, ClusterIP Service, and ConfigMap.
- [`.github/workflows/ci-cd.yml`](./.github/workflows/ci-cd.yml) — GitHub Actions CI/CD pipeline.
- [`requirements.txt`](./requirements.txt) — Dependency specifications.
- [`README.md`](./README.md) — Architectural overview, rubric mapping, and local setup guide.

---

## 3. Recent Changes History
- **2026-11-09 (Initial Microservice Implementation):**
  - Scaffolded `Studium-Notifications` in Python 3.12 with FastAPI and Amazon DynamoDB, fulfilling Rubric R1 (2nd language and 2nd DBMS).
  - Implemented `wolverine_unpack.py` capable of decoding JasperFx .NET binary envelopes from `studium-notifications-queue`.
  - Implemented `handlers.py` processing `ReservationNotificationEvent`, `WaitlistSlotAvailableEvent`, and `RoomMaintenanceEvent`.
  - Implemented `DynamoDbService` with automatic table creation and GSI `UserIdIndex`.
  - Implemented REST API routes for user notification feed (`GET /api/notifications`), marking as read, and manual testing.
  - Implemented `test_wolverine_unpack.py`, `test_handlers.py`, and `test_api.py` (10 passing unit tests).
  - Added production Dockerfile, `k8s/deployment.yaml`, and `.github/workflows/ci-cd.yml`.
