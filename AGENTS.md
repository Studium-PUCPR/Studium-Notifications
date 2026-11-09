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

### 1.3 Asynchronous Messaging via RabbitMQ (Rubric R3 Anchor)
- **Problem Solved:** Connects Python FastAPI service to the platform RabbitMQ message broker (`studium-rabbitmq-service.studium.svc.cluster.local:5672`) consuming `studium-notifications-queue`.
- **Chosen Solution:** Uses `aio-pika` for async AMQP consumption. Features `unpack_rabbitmq_message` in `wolverine_unpack.py` capable of decoding both Wolverine .NET binary envelopes and JSON payloads.
- **Legacy branch:** AWS SQS version preserved on branch `origin/sqs`.

### 1.4 Background Worker & Lifespan Architecture
- Uses FastAPI lifespan context manager (`@asynccontextmanager`) to manage the background `RabbitMqNotificationWorker`.
- Automatically provisions the DynamoDB table if it does not exist on initial startup.
- Connects robustly to RabbitMQ, processes messages, persists items in DynamoDB, and dispatches simulated email alerts.

---

## 2. Project Structure & File Map
- **`app/`:**
  - `main.py` — Composition root, FastAPI app, CORS, lifespan startup/shutdown, and `/health` probe.
  - `config.py` — Pydantic `BaseSettings` reading environment variables (RabbitMQ URL, DynamoDB table).
  - `models/notification.py` — Pydantic domain models: `NotificationType`, `NotificationItem`, `NotificationResponse`, `NotificationListResponse`.
  - `consumer/wolverine_unpack.py` — Binary Wolverine C# envelope decoder, RabbitMQ unpacker, and JSON parser.
  - `consumer/handlers.py` — Event dispatchers transforming incoming events into localized student notifications.
  - `consumer/worker.py` — Async background consumer loop over RabbitMQ queue using `aio-pika`.
  - `services/dynamodb_service.py` — DynamoDB table management, put_item, query, update_item, and ping.
  - `services/email_service.py` — SES / simulated email dispatcher.
  - `api/routes.py` — REST endpoints (`GET /api/notifications`, `PATCH /api/notifications/{id}/read`, `POST /api/notifications/test`).
- **`tests/`:**
  - `test_wolverine_unpack.py` — Tests decoding Wolverine binary envelopes, raw JSON, and RabbitMQ payloads.
  - `test_handlers.py` — Tests event mapping (ReservationCreated, NoShowRecorded, WaitlistSlotAvailable, RoomMaintenance).
  - `test_api.py` — FastAPI TestClient testing health probe and notification feed CRUD.
- [`Dockerfile`](./Dockerfile) — Multi-stage production container with Python 3.12-slim and non-root user.
- [`k8s/deployment.yaml`](./k8s/deployment.yaml) — Kubernetes Deployment, ClusterIP Service, and ConfigMap.
- [`.github/workflows/ci-cd.yml`](./.github/workflows/ci-cd.yml) — GitHub Actions CI/CD pipeline.
- [`requirements.txt`](./requirements.txt) — Dependency specifications including `aio-pika`.
- [`README.md`](./README.md) — Architectural overview, rubric mapping, and local setup guide.

---

## 3. Recent Changes History
- **2026-11-09 (Migrated Messaging from AWS SQS to RabbitMQ):**
  - Added `aio-pika` to `requirements.txt` and environment.
  - Implemented `RabbitMqNotificationWorker` in `app/consumer/worker.py` and `unpack_rabbitmq_message` in `app/consumer/wolverine_unpack.py`.
  - Updated `app/main.py` to start and manage `RabbitMqNotificationWorker` during app lifespan.
  - Updated `k8s/deployment.yaml` with `RABBITMQ_URL` and `RABBITMQ_NOTIFICATIONS_QUEUE_NAME`.
  - Added unit tests in `test_wolverine_unpack.py` for RabbitMQ message unpacking; all 12 tests passing.
  - SQS version preserved on branch `origin/sqs`.
- **2026-11-09 (Initial Microservice Implementation):**
  - Scaffolded `Studium-Notifications` in Python 3.12 with FastAPI and Amazon DynamoDB, fulfilling Rubric R1.
