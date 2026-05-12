## Deploy to AWS ECS (Fargate)

This deployment runs the new Holdings stack as one Fargate task with two essential containers:

- `holdings-frontend`: Next.js on port `3000`
- `holdings-backend`: FastAPI on port `8000`

Use an Application Load Balancer with two target groups. Route `/api/*` to the backend target group and all other paths to the frontend target group.

### Build Locally

```bash
docker build -f backend/Dockerfile -t holdings-backend:local .
docker build -f frontend/Dockerfile -t holdings-frontend:local frontend
```

Optional smoke checks:

```bash
docker run --rm -p 8000:8000 holdings-backend:local
# Open http://localhost:8000/api/health

docker run --rm -p 3000:3000 -e API_BASE_URL=http://host.docker.internal:8000 holdings-frontend:local
# Open http://localhost:3000
```

### Push Images To ECR

Replace `<REGION>`, `<ACCOUNT_ID>`, and `<TAG>`.

```bash
aws ecr create-repository --repository-name holdings-backend
aws ecr create-repository --repository-name holdings-frontend

aws ecr get-login-password --region <REGION> \
  | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com

docker build -f backend/Dockerfile -t holdings-backend:<TAG> .
docker tag holdings-backend:<TAG> <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/holdings-backend:<TAG>
docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/holdings-backend:<TAG>

docker build -f frontend/Dockerfile -t holdings-frontend:<TAG> frontend
docker tag holdings-frontend:<TAG> <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/holdings-frontend:<TAG>
docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/holdings-frontend:<TAG>
```

### Register The Task Definition

Update `ecs/TASKDEF.template.json` with your AWS account, region, tag, task roles, and any SSM parameter ARNs you use.

```bash
aws ecs register-task-definition \
  --cli-input-json file://ecs/TASKDEF.template.json
```

The frontend container uses `API_BASE_URL=http://127.0.0.1:8000`, which works because both containers share the same task network namespace.

### Create The ECS Service

1. Create an ECS cluster using Fargate.
2. Create a CloudWatch log group named `/ecs/holdings`.
3. Create two ALB target groups:
   - Frontend target group: HTTP `3000`, health check path `/`
   - Backend target group: HTTP `8000`, health check path `/api/health`
4. Create an ALB listener:
   - Rule `/api/*` forwards to the backend target group.
   - Default action forwards to the frontend target group.
5. Create one ECS service from the `holdings-next-fastapi` task definition and attach both target groups:
   - `holdings-frontend` container, port `3000`
   - `holdings-backend` container, port `8000`

### Secrets

Store optional secrets in SSM Parameter Store or Secrets Manager and reference them from the task definition:

- `OPENAI_API_KEY`
- `PLAID_CLIENT_ID`
- `PLAID_SECRET`

If you do not use OpenAI or Plaid, remove those entries from the task definition before registering it.

### Persistence

By default, the backend writes SQLite state to `/app/runtime/vaultboard.db` inside the Fargate task. That storage is ephemeral and can reset when tasks are replaced.

For durable app state, mount EFS at `/app/runtime` or migrate the persistence layer to an external database before relying on ECS for long-lived production data.

