# Studium-Notifications

Stack: `Python 3.12` + `FastAPI` + `Amazon DynamoDB` (`studium_notifications`) + `Amazon SES` simulation.

> **Synchronous Inter-Service Architecture:** Serves as the platform's synchronous notification dispatch and feed microservice via canonical REST API (`POST /api/notifications`). Cross-language .NET callers invoke this service via `INotificationsClient`. A legacy SQS version is preserved on branch `origin/sqs`.

## Rubric R1, R2 & R3 Anchors
* **Technological Diversity (R1):** Introduces **Python** as the second distinct programming language in the platform (complementing C# / .NET 10) and **Amazon DynamoDB** as the second distinct DBMS (NoSQL Key-Value / Document store complementing PostgreSQL).
* **Database per Service (R1):** Isolated persistence on a dedicated DynamoDB table (`studium_notifications`) with On-Demand capacity and a Global Secondary Index (`UserIdIndex`).
* **Containerization & EKS (R2):** Packaged via multi-stage Python 3.12-slim Dockerfile, running under the `studium` namespace on Amazon EKS with health probes and ClusterIP Service (`studium-notifications-service:80`).
* **Synchronous Inter-Service Communication:** Receives synchronous HTTP REST dispatches (`POST /api/notifications`) from upstream .NET microservices (`Studium-Booking`, `Studium-Users`, `Studium-Catalog`).

## Scope & Capabilities
- **Synchronous Notification Ingestion:** `POST /api/notifications` allows any internal microservice or administrator to dispatch alerts immediately with guaranteed persistence.
- **In-App Notification Feed (UC018):** Chronological, user-specific feed of operational alerts under `/api/notifications?user_id={id}`.
- **Read Status Tracking:** Mark notifications as read under `PATCH /api/notifications/{id}/read`.
- **Simulated SES Email Alerts:** Dispatches email notifications on critical reservation milestones and infractions.

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
