#!/bin/bash

# Complete ECS Fargate Deployment Script
set -e

# Load configuration
if [ -f "aws-config.env" ]; then
    source aws-config.env
else
    echo "❌ aws-config.env not found. Run aws-setup.sh first."
    exit 1
fi

echo "🚀 Starting ECS Fargate deployment..."

# Step 1: Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"

echo "📦 Building and pushing Docker image..."

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URI

# Build and tag image
docker build -t $ECR_REPOSITORY .
docker tag $ECR_REPOSITORY:latest $ECR_URI:latest

# Push image
docker push $ECR_URI:latest

echo "✅ Image pushed to ECR: $ECR_URI:latest"

# Step 2: Create task definition
echo "📝 Creating task definition..."

cat > task-definition.json << EOF
{
  "family": "$TASK_FAMILY",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "amygdala-backend",
      "image": "$ECR_URI:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "secrets": [
        {
          "name": "SUPABASE_URL",
          "valueFrom": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/amygdala/supabase-url"
        },
        {
          "name": "SUPABASE_SERVICE_ROLE_KEY",
          "valueFrom": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/amygdala/supabase-service-role-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/$TASK_FAMILY",
          "awslogs-region": "$AWS_REGION",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/healthz || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      },
      "essential": true
    }
  ]
}
EOF

# Register task definition
TASK_DEFINITION_ARN=$(aws ecs register-task-definition \
    --cli-input-json file://task-definition.json \
    --region $AWS_REGION \
    --query "taskDefinition.taskDefinitionArn" \
    --output text)

echo "✅ Task definition registered: $TASK_DEFINITION_ARN"

# Step 3: Create or update ECS service
echo "🔄 Creating ECS service..."

# Convert subnet IDs to array format
SUBNET_ARRAY=$(echo $SUBNET_IDS | sed 's/ /","/g' | sed 's/^/"/' | sed 's/$/"/')

# Check if service exists
if aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $AWS_REGION --query "services[0].serviceName" --output text 2>/dev/null | grep -q $SERVICE_NAME; then
    echo "🔄 Updating existing service..."
    aws ecs update-service \
        --cluster $CLUSTER_NAME \
        --service $SERVICE_NAME \
        --task-definition $TASK_FAMILY \
        --region $AWS_REGION
else
    echo "🆕 Creating new service..."
    aws ecs create-service \
        --cluster $CLUSTER_NAME \
        --service-name $SERVICE_NAME \
        --task-definition $TASK_FAMILY \
        --desired-count 1 \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_ARRAY],securityGroups=[$ECS_SG_ID],assignPublicIp=ENABLED}" \
        --load-balancers "targetGroupArn=$TARGET_GROUP_ARN,containerName=amygdala-backend,containerPort=8000" \
        --region $AWS_REGION
fi

echo "✅ Service deployment initiated"

# Step 4: Wait for service to be stable
echo "⏳ Waiting for service to become stable..."
aws ecs wait services-stable \
    --cluster $CLUSTER_NAME \
    --services $SERVICE_NAME \
    --region $AWS_REGION

echo "🎉 Deployment completed successfully!"

# Step 5: Display service information
echo ""
echo "📊 Deployment Summary:"
echo "🌐 Load Balancer URL: http://$ALB_DNS"
echo "🔍 Health Check: http://$ALB_DNS/healthz"
echo "📡 Webhook URL: http://$ALB_DNS/webhooks/bluebubbles"
echo ""
echo "📋 Useful commands:"
echo "  View logs: aws logs tail /ecs/$TASK_FAMILY --follow --region $AWS_REGION"
echo "  Check service: aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $AWS_REGION"
echo "  Scale service: aws ecs update-service --cluster $CLUSTER_NAME --service $SERVICE_NAME --desired-count 2 --region $AWS_REGION"

# Cleanup
rm -f task-definition.json

echo "✨ Deployment complete!"
