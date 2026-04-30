## Deploy to AWS ECS (Fargate)

This repo is a Streamlit app. The recommended AWS path is:

- **ECR** for container images
- **ECS Fargate** for running tasks
- **Application Load Balancer (ALB)** for HTTPS + routing

### Build and run locally (Docker)

```bash
docker build -t holdings:local .
docker run --rm -p 8501:8501 holdings:local
```

### Push image to ECR

Replace `<REGION>` and `<ACCOUNT_ID>`.

```bash
aws ecr create-repository --repository-name holdings

aws ecr get-login-password --region <REGION> \
  | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com

docker build -t holdings:latest .
docker tag holdings:latest <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/holdings:latest
docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/holdings:latest
```

### ECS service (console)

1. Create an **ECS Cluster** (Networking only / Fargate).
2. Create a **Task Definition** (Fargate):
   - Container port: **8501**
   - Health check: keep Dockerfile healthcheck (ECS will use it)
   - Logs: CloudWatch (create group `/ecs/holdings`)
3. Create a **Service**:
   - Launch type: **Fargate**
   - Desired tasks: **1**
   - Attach an **ALB**
   - Target group health check path: `/`
4. In the ALB listener, route traffic to the target group.

### Secrets

If you use OpenAI flags, store `OPENAI_API_KEY` in either:
- **SSM Parameter Store** (recommended), or
- **Secrets Manager**

Then reference it in the task definition (see `TASKDEF.template.json`).

### Auth0 (OIDC) in front of Streamlit

Put **oauth2-proxy** in front of this container instead of exposing Streamlit directly. See **`deploy/oauth2-proxy/README.md`** for Auth0 settings, callback URLs, and a second container in the same ECS task.

