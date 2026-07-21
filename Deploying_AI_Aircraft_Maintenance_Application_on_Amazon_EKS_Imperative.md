# Deploying the AI Aircraft Maintenance Application on Amazon EKS (Imperative Deployment)

This guide demonstrates how to deploy the React frontend and FastAPI
backend application on Amazon EKS using imperative Kubernetes commands.

------------------------------------------------------------------------

# Prerequisites

Before deploying, ensure the following are ready:

-   AWS CLI installed and configured
-   kubectl installed
-   Docker installed
-   Amazon EKS Cluster created
-   EKS Worker Node Group created
-   Amazon ECR repositories created
-   Backend Docker image pushed to Amazon ECR
-   Frontend Docker image pushed to Amazon ECR

------------------------------------------------------------------------

# Step 0: Create Amazon EKS Cluster

Before deploying the application, create an Amazon EKS Cluster and a
Managed Node Group.

------------------------------------------------------------------------

## Create the EKS Cluster

1.  Open the AWS Console.
2.  Navigate to **Amazon EKS**.
3.  Click **Create cluster**.
4.  Choose **Custom configuration**.
5.  Enter the Cluster Name.
6.  Select the latest Kubernetes version.
7.  Create or select the recommended Cluster IAM Role.
8.  Select the default VPC (or your custom VPC).
9.  Select at least two subnets in different Availability Zones.
10. Enable the Public API Endpoint.
11. Disable **EKS Auto Mode** (recommended for this tutorial).
12. Create the cluster.

Wait until the cluster status becomes **Active**.

------------------------------------------------------------------------

## Create the Managed Node Group

1.  Open the EKS Cluster.
2.  Navigate to **Compute**.
3.  Click **Add Node Group**.
4.  Create or select the recommended Node IAM Role.
5.  Choose:
    -   Amazon Linux 2023
    -   On-Demand Capacity
    -   Instance Type: `t3.medium`
6.  Configure Scaling.

```{=html}
<!-- -->
```
    Desired Size : 2
    Minimum Size : 1
    Maximum Size : 2

7.  Click **Create**.

Wait until the Node Group status becomes **Active**.

------------------------------------------------------------------------

## Required IAM Policies for the Worker Node Role

The Worker Node IAM Role must have the following AWS managed policies
attached.

-   AmazonEKSWorkerNodePolicy
-   AmazonEC2ContainerRegistryReadOnly
-   AmazonEKS_CNI_Policy

If any of these policies are missing, the Node Group may fail with

    NodeCreationFailure

    Instances failed to join the kubernetes cluster

------------------------------------------------------------------------

# Step 1: Connect kubectl to Amazon EKS

Update kubeconfig.

``` bash
aws eks update-kubeconfig --region us-east-1 --name <EKS_CLUSTER_NAME>
```

Verify the current context.

``` bash
kubectl config current-context
```

Verify the Worker Nodes.

``` bash
kubectl get nodes
```

------------------------------------------------------------------------

## kubectl Authentication Error

If

``` bash
kubectl get nodes
```

returns

    error: You must be logged in to the server

    the server has asked for the client to provide credentials

Navigate to

    Amazon EKS
    → Cluster
    → Access
    → Create Access Entry

Create an Access Entry for the IAM User and attach

    AmazonEKSClusterAdminPolicy

Wait a minute and retry.

``` bash
kubectl get nodes
```

------------------------------------------------------------------------

# Step 2: Create Backend Deployment

``` bash
kubectl create deployment maintenance-backend --image=<BACKEND_ECR_IMAGE_URI>
```

Verify.

``` bash
kubectl get deployments
```

------------------------------------------------------------------------

# Step 3: Expose Backend

``` bash
kubectl expose deployment maintenance-backend --type=LoadBalancer --port=80 --target-port=8000
```

Check service.

``` bash
kubectl get svc
```

Wait until an External IP / DNS name is assigned.

------------------------------------------------------------------------

# Step 4: Configure AWS Credentials

The backend communicates with Amazon Bedrock. Therefore, AWS credentials
must be available inside the pod.

Create the Kubernetes Secret.

``` bash
kubectl create secret generic aws-credentials --from-literal=AWS_ACCESS_KEY_ID=<AWS_ACCESS_KEY_ID> --from-literal=AWS_SECRET_ACCESS_KEY=<AWS_SECRET_ACCESS_KEY> --from-literal=AWS_REGION=us-east-1
```

Verify.

``` bash
kubectl get secrets
```

Inject the Secret.

``` bash
kubectl set env deployment/maintenance-backend --from=secret/aws-credentials
```

Restart deployment.

``` bash
kubectl rollout restart deployment maintenance-backend
```

Verify rollout.

``` bash
kubectl rollout status deployment maintenance-backend
```

------------------------------------------------------------------------

# Step 5: Verify Backend

Open

    http://<BACKEND_LOAD_BALANCER>

or

    http://<BACKEND_LOAD_BALANCER>/docs

The FastAPI Swagger page should load successfully.

------------------------------------------------------------------------

# Step 6: Create Frontend Deployment

``` bash
kubectl create deployment maintenance-frontend --image=<FRONTEND_ECR_IMAGE_URI>
```

Verify.

``` bash
kubectl get deployments
```

------------------------------------------------------------------------

# Step 7: Expose Frontend

``` bash
kubectl expose deployment maintenance-frontend --type=LoadBalancer --port=80 --target-port=3000
```

Verify.

``` bash
kubectl get svc
```

Wait until the External DNS becomes available.

------------------------------------------------------------------------

# Step 8: Update Frontend Backend URL

Initially the frontend points to localhost.

Update

    .env

Replace

    VITE_API_BASE_URL=http://localhost:8000

with

    VITE_API_BASE_URL=http://<BACKEND_LOAD_BALANCER_DNS>

------------------------------------------------------------------------

# Step 9: Configure Vite

While accessing the application from the AWS Load Balancer, Vite blocks
unknown hosts.

Update

`vite.config.js`

``` javascript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react],
  server: {
    host: "0.0.0.0",
    port: 3000,
    allowedHosts: true
  }
});
```

This allows requests coming through the AWS Load Balancer.

------------------------------------------------------------------------

# Step 10: Rebuild Frontend Image

``` bash
docker build -t maintenance-frontend .
```

Tag the image.

``` bash
docker tag maintenance-frontend:latest <FRONTEND_ECR_IMAGE_URI>
```

Push to ECR.

``` bash
docker push <FRONTEND_ECR_IMAGE_URI>
```

Restart deployment.

``` bash
kubectl rollout restart deployment maintenance-frontend
```

------------------------------------------------------------------------

# Step 11: Verify Application

Check Deployments

``` bash
kubectl get deployments
```

Check Pods

``` bash
kubectl get pods
```

Check Services

``` bash
kubectl get svc
```

Open the frontend Load Balancer URL.

Verify:

-   Frontend loads successfully
-   Backend API is reachable
-   Amazon Bedrock generates responses successfully

------------------------------------------------------------------------

# Useful kubectl Commands

View all resources

``` bash
kubectl get all
```

Describe deployment

``` bash
kubectl describe deployment maintenance-backend
```

Describe pod

``` bash
kubectl describe pod <POD_NAME>
```

View logs

``` bash
kubectl logs <POD_NAME>
```

Restart deployment

``` bash
kubectl rollout restart deployment maintenance-backend
```

Scale deployment

``` bash
kubectl scale deployment maintenance-backend --replicas=2
```

Delete deployment

``` bash
kubectl delete deployment maintenance-backend
```

Delete service

``` bash
kubectl delete svc maintenance-backend
```

------------------------------------------------------------------------

# Troubleshooting

## 1. kubectl Access Denied

If

    kubectl get nodes

returns Access Denied:

-   Verify IAM user has AdministratorAccess.
-   Create an EKS Access Entry.
-   Attach **AmazonEKSClusterAdminPolicy**.

------------------------------------------------------------------------

## 2. Worker Nodes Not Joining

If the Node Group status is **NodeCreationFailure**:

-   Verify the worker node IAM role.
-   Attach:
    -   AmazonEKSWorkerNodePolicy
    -   AmazonEC2ContainerRegistryReadOnly
    -   AmazonEKS_CNI_Policy

------------------------------------------------------------------------

## 3. Backend Cannot Access Amazon Bedrock

If logs show

    NoCredentialsError

Verify the Kubernetes Secret exists.

``` bash
kubectl get secrets
```

Restart the deployment after injecting the secret.

------------------------------------------------------------------------

## 4. Frontend Opens but API Doesn't Work

Verify

    VITE_API_BASE_URL

points to the Backend Load Balancer DNS.

Rebuild and push the Docker image.

------------------------------------------------------------------------

## 5. Vite Blocks the AWS Load Balancer

Error:

    Blocked request.
    This host is not allowed.

Update `vite.config.js`

``` javascript
server: {
    host: "0.0.0.0",
    port: 3000,
    allowedHosts: true
}
```

Rebuild and redeploy the frontend.

------------------------------------------------------------------------

## 6. External Load Balancer Not Created

Check

``` bash
kubectl get svc
```

Wait a few minutes.

AWS needs time to provision the Load Balancer.

------------------------------------------------------------------------

# Architecture

``` text
User
      │
      ▼
React Frontend
      │
 REST API
      ▼
FastAPI Backend
      │
      ▼
Amazon Bedrock
```

Both services are containerized using Docker and deployed on Amazon EKS.

------------------------------------------------------------------------

# Next Step

In the next section, we'll move to the production-ready approach by:

-   Writing Kubernetes YAML manifests
-   Organizing manifests in a dedicated `kubernetes/` folder
-   Deploying declaratively
-   Automating deployments with GitHub Actions
-   Building a complete CI/CD pipeline
