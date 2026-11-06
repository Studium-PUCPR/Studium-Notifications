# Studium-Notifications 

Stack: Python (FastAPI) or Node.js (TypeScript/Express) + MongoDB (db-notifications).

Why keep this separate instead of merging into Users: With a 5-person team, Rubric R1 requires each member to implement and present at least one microservice, and requires at least 2 languages and 2 DBMSs. Having Member 5 build Studium-Notifications as a lightweight Python/Node service backed by MongoDB (or DynamoDB) satisfies both the 5th team member requirement and the multi-language/multi-DB rubric requirement in one stroke.   

Scope: Consumes from the studium-notifications-queue (SQS subscribed to the SNS topics), checks user preferences, stores the alert in MongoDB to serve the in-app Notificações feed (UC018 / M17), and sends emails via Amazon SES.   
