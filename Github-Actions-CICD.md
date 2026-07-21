# GitHub Actions CI/CD Deployment Guide

## AI Aircraft Maintenance Platform

In the previous section we manually deployed the application to Amazon EKS using imperative `kubectl` commands.

In this section, we'll completely automate the deployment process using **GitHub Actions**.

Every time code is pushed to GitHub, the pipeline will:

- Build the Backend Docker Image
- Build the Frontend Docker Image
- Push both images to Amazon ECR
- Connect to Amazon EKS
- Deploy the latest application
- Verify the deployment

---

# CI/CD Architecture

```
Developer

↓

Git Push

↓

GitHub Repository

↓

GitHub Actions

↓

Checkout Repository

↓

Configure AWS Credentials

↓

Login to Amazon ECR

↓

Build Backend Docker Image

↓

Push Backend Image

↓

Build Frontend Docker Image

↓

Push Frontend Image

↓

Configure kubectl

↓

Deploy Kubernetes Resources

↓

Verify Deployment

↓

Amazon EKS
```

---

# Project Structure

```
AI-Aircraft-Maintenance-Platform
│
├── .github
│   └── workflows
│       └── deploy.yml
│
├── backend
│   ├── Dockerfile
│   └── ...
│
├── frontend
│   ├── Dockerfile
│   └── ...
│
├── kubernetes
│   ├── backend-deployment.yaml
│   ├── backend-service.yaml
│   ├── frontend-deployment.yaml
│   └── frontend-service.yaml
│
└── README.md
```

---

# Step 1 - Create GitHub Secrets

Navigate to

```
Repository

↓

Settings

↓

Secrets and Variables

↓

Actions
```

Create the following repository secrets.

| Secret Name | Description |
|-------------|-------------|
| AWS_ACCESS_KEY_ID | AWS Access Key |
| AWS_SECRET_ACCESS_KEY | AWS Secret Key |
| AWS_REGION | us-east-1 |
| AWS_ACCOUNT_ID | AWS Account ID |
| EKS_CLUSTER_NAME | Amazon EKS Cluster Name |
| BACKEND_IMAGE | Backend ECR Image URI |
| FRONTEND_IMAGE | Frontend ECR Image URI |

Example

```
BACKEND_IMAGE

494810891651.dkr.ecr.us-east-1.amazonaws.com/maintenance-backend:latest
```

```
FRONTEND_IMAGE

494810891651.dkr.ecr.us-east-1.amazonaws.com/maintenance-frontend:latest
```

---

# Step 2 - Kubernetes Deployment Files

Inside

```
kubernetes/
```

create

```
backend-deployment.yaml

backend-service.yaml

frontend-deployment.yaml

frontend-service.yaml
```

Use placeholders for the Docker images.

Backend

```yaml
image: ${BACKEND_IMAGE}
```

Frontend

```yaml
image: ${FRONTEND_IMAGE}
```

GitHub Actions will automatically replace these placeholders during deployment.

---

# Step 3 - GitHub Actions Workflow

Create

```
.github/workflows/deploy.yml
```

This workflow automatically performs all deployment tasks.

---

## Repository Checkout

Downloads the latest source code.

---

## Configure AWS Credentials

Authenticates GitHub Actions with AWS.

Uses

```
AWS_ACCESS_KEY_ID

AWS_SECRET_ACCESS_KEY
```

---

## Login to Amazon ECR

Authenticates Docker with Amazon ECR.

---

## Build Docker Images

GitHub Actions automatically builds both Docker images.

Backend

```
backend/
```

Frontend

```
frontend/
```

---

## Push Docker Images

The workflow automatically pushes both images to Amazon ECR.

No manual Docker commands are required.

---

## Configure kubectl

GitHub Actions connects to Amazon EKS.

```
aws eks update-kubeconfig
```

---

## Update Kubernetes Manifest

GitHub Actions replaces

```
${BACKEND_IMAGE}

${FRONTEND_IMAGE}
```

with the actual image URIs stored in GitHub Secrets.

---

## Deploy Application

Automatically deploys

```
backend-deployment.yaml

backend-service.yaml

frontend-deployment.yaml

frontend-service.yaml
```

using

```bash
kubectl apply -f kubernetes/
```

---

## Verify Deployment

The workflow waits until both deployments become healthy.

Backend

```bash
kubectl rollout status deployment/maintenance-backend
```

Frontend

```bash
kubectl rollout status deployment/maintenance-frontend
```

Finally, it verifies the resources.

```bash
kubectl get deployments

kubectl get pods

kubectl get svc
```

---

# Complete Deployment Flow

```
Developer

↓

git push

↓

GitHub Actions

↓

Build Backend Image

↓

Push Backend Image

↓

Build Frontend Image

↓

Push Frontend Image

↓

Connect to Amazon EKS

↓

Deploy Kubernetes Resources

↓

Verify Deployment

↓

Application Live
```

---

# Advantages of CI/CD

Instead of manually running

- docker build
- docker tag
- docker push
- kubectl apply
- kubectl rollout

GitHub Actions performs everything automatically.

The only action required from the developer is

```
git add .

git commit -m "Updated application"

git push origin master
```

Everything else happens automatically.

---

# Next Improvements

This implementation uses the `latest` image tag for simplicity.

For production deployments, consider:

- Git Commit SHA image versioning
- IAM Roles for Service Accounts (IRSA)
- ConfigMaps
- Kubernetes Secrets
- Ingress Controller
- Helm Charts
- ArgoCD / GitOps

These enhancements make the deployment more scalable and production-ready.