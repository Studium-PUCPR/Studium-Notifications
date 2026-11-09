# Studium-Notifications — Project State & Agent Context (`AGENTS.md`)

> **MANDATORY AGENT DIRECTIVE:**
> After **every user prompt**, always evaluate whether we reached a useful architectural conclusion, resolved a design question, or made code/configuration changes. If so, **update both the relevant sections and Section 3 (`Recent Changes History`) in this `./AGENTS.md` file before finishing your turn** so any future chat session immediately has full context of the project state.

---

## 1. Architectural Decisions & Conclusions Log

### 1.1 Python 3.12 & FastAPI for Tech Diversity (Rubric R1 Anchor)
- **Problem Solved:** Rubric R1 mandates that the platform must employ at least **two distinct programming languages** and at least **two distinct DBMSs**. The existing backend services (`Studium-Users`, `Studium-Catalog`, `Studium-Booking`, `Studium-Audit`) were implemented in C# (.NET 10) with PostgreSQL.
- **Chosen Solution:** Implemented `Studium-Notifications` using **Python 3.12** and **FastAPI**, providing high-performance asynchronous event processing and a modern REST API.

### 1.2 Amazon DynamoDB with Automated 3-Day TTL & Secondary DBMS (Rubric R1 Anchor)
- **Problem Solved:** Fulfills the requirement for two different DBMS technologies while maintaining the Database-per-Service principle and preventing infinite storage growth.
- **Chosen Solution:** Amazon DynamoDB (managed NoSQL key-value/document store):
  - Table: `studium_notifications`
  - Partition Key: `notification_id` (String UUID)
  - Global Secondary Index (GSI): `UserIdIndex` with Partition Key `user_id` (String) and Sort Key `created_at` (String ISO 8601 UTC) for instant chronological user feed queries.
  - Billing Mode: `PAY_PER_REQUEST` (On-Demand capacity).
  - Time To Live (TTL): Configured 3-day TTL attribute `ttl` (epoch seconds = `now + 259200s`) automatically enabling DynamoDB item expiration and pruning without maintenance jobs.

### 1.3 Singleton Connection Pooling & Health Segregation
- **Problem Solved:** Prevents botocore / urllib3 connection churn on repeated HTTP requests and isolates shallow container liveness from DynamoDB network dependency.
- **Chosen Solution:** Configured cached singleton `DynamoDbService` instance dependency across API routes and application lifespan. Segregated shallow liveness (`/health`) from deep database readiness (`/health/ready` via `dynamo.ping()`).

### 1.4 Pure Synchronous REST Inter-Service Architecture
- **Problem Solved:** Eliminates the complexity and cognitive clutter of decoding .NET Wolverine binary envelopes in Python (`wolverine_unpack.py`). Provides a dedicated synchronous REST endpoint (`POST /api/notifications`) for upstream .NET microservices (`Studium-Booking`, `Studium-Users`, `Studium-Catalog`), satisfying the requirement for synchronous inter-service communication.
- **Legacy branch:** AWS SQS and RabbitMQ consumer versions are preserved on branches `origin/sqs` and git commit history.

---

## 2. Project Structure & File Map
- **`app/`:**
  - `main.py` — Composition root, FastAPI app, CORS, lifespan table verification, `/health` liveness, and `/health/ready` readiness probe.
  - `config.py` — Pydantic `BaseSettings` reading environment variables (DynamoDB table, AWS credentials).
  - `models/notification.py` — Pydantic domain models: `NotificationType`, `NotificationItem`, `NotificationResponse`, `NotificationListResponse`, `CreateNotificationRequest`.
  - `services/dynamodb_service.py` — DynamoDB table management, put_item with 3-day TTL, query, update_item, and ping.
  - `services/email_service.py` — SES / simulated email dispatcher.
  - `api/routes.py` — REST endpoints (`GET /api/notifications`, `POST /api/notifications`, `PATCH /api/notifications/{id}/read`, `POST /api/notifications/test`) with singleton dependency injection.
- **`tests/`:**
  - `test_api.py` — FastAPI TestClient testing health probe, readiness probe, notification feed CRUD, and 3-day TTL expiration.
- [`Dockerfile`](./Dockerfile) — Multi-stage production container with Python 3.12-slim and non-root user.
- [`k8s/deployment.yaml`](./k8s/deployment.yaml) — Kubernetes Deployment, ClusterIP Service, and ConfigMap with readiness probe configured to `/health/ready`.

---

## 3. Recent Changes History
- **2026-11-09 (DynamoDB 3-Day TTL, Singleton Pooling & Deep Readiness Probe):**
  - Added 3-day TTL attribute `ttl` to `NotificationItem`, `NotificationResponse`, and DynamoDB item persistence (`now + 3 days` epoch seconds).
  - Enabled native DynamoDB TTL on attribute `ttl` in `ensure_table_exists()`.
  - Implemented singleton dependency caching for `DynamoDbService` to reuse botocore HTTP connection pooling.
  - Segregated shallow `/health` liveness probe from deep `/health/ready` readiness probe, and updated `k8s/deployment.yaml`.
  - Updated API unit test suite and verified all tests pass.
- **2026-11-09 (Transition to Pure Synchronous REST Service):**
  - Removed `wolverine_unpack.py`, background AMQP consumer worker, and `aio-pika` dependency.
  - Promoted `POST /api/notifications` to the canonical synchronous endpoint for cross-service dispatches.
  - All 3 API unit tests passing with `pytest`.
- **2026-11-09 (RabbitMQ Migration & SQS Storage Branch):**
  - Migrated async consumer to `aio-pika` over RabbitMQ AMQP broker (`studium-rabbitmq-service:5672`).
- **2026-11-08 (Initial Implementation & Deployment):**
  - Scaffolded Python 3.12 + FastAPI microservice with Amazon DynamoDB and Wolverine SQS unpacker.
