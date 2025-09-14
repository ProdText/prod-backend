#!/bin/bash

# AWS ECS Fargate Setup Script
set -e

# Configuration
AWS_REGION="us-east-2"
CLUSTER_NAME="amygdala-cluster"
SERVICE_NAME="amygdala-service"
TASK_FAMILY="amygdala-backend"
ECR_REPOSITORY="amygdala-backend"

echo "🚀 Setting up AWS infrastructure for ECS Fargate deployment..."

# Step 1: Create IAM execution role for ECS tasks
echo "📋 Creating ECS task execution role..."

# Check if role exists
if ! aws iam get-role --role-name ecsTaskExecutionRole --region $AWS_REGION 2>/dev/null; then
    # Create trust policy
    cat > trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Create the role
    aws iam create-role \
        --role-name ecsTaskExecutionRole \
        --assume-role-policy-document file://trust-policy.json \
        --region $AWS_REGION

    # Attach the managed policy
    aws iam attach-role-policy \
        --role-name ecsTaskExecutionRole \
        --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy \
        --region $AWS_REGION

    # Attach additional policy for Parameter Store (for secrets)
    aws iam attach-role-policy \
        --role-name ecsTaskExecutionRole \
        --policy-arn arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess \
        --region $AWS_REGION

    rm trust-policy.json
    echo "✅ ECS task execution role created"
else
    echo "✅ ECS task execution role already exists"
fi

# Step 2: Create ECS cluster
echo "🏗️ Creating ECS cluster..."
aws ecs create-cluster \
    --cluster-name $CLUSTER_NAME \
    --capacity-providers FARGATE \
    --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
    --region $AWS_REGION 2>/dev/null || echo "✅ Cluster already exists"

# Step 3: Create ECR repository
echo "📦 Creating ECR repository..."
aws ecr create-repository \
    --repository-name $ECR_REPOSITORY \
    --region $AWS_REGION 2>/dev/null || echo "✅ ECR repository already exists"

# Step 4: Create CloudWatch log group
echo "📊 Creating CloudWatch log group..."
aws logs create-log-group \
    --log-group-name "/ecs/$TASK_FAMILY" \
    --region $AWS_REGION 2>/dev/null || echo "✅ Log group already exists"

# Step 5: Get default VPC and subnets
echo "🌐 Getting VPC information..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query "Vpcs[0].VpcId" --output text --region $AWS_REGION)
SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query "Subnets[*].SubnetId" --output text --region $AWS_REGION)

echo "VPC ID: $VPC_ID"
echo "Subnet IDs: $SUBNET_IDS"

# Step 6: Create security group for ALB
echo "🔒 Creating security group for Application Load Balancer..."
ALB_SG_ID=$(aws ec2 create-security-group \
    --group-name amygdala-alb-sg \
    --description "Security group for Amygdala ALB" \
    --vpc-id $VPC_ID \
    --query "GroupId" \
    --output text \
    --region $AWS_REGION 2>/dev/null || \
    aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=amygdala-alb-sg" \
    --query "SecurityGroups[0].GroupId" \
    --output text \
    --region $AWS_REGION)

# Allow HTTP and HTTPS traffic to ALB
aws ec2 authorize-security-group-ingress \
    --group-id $ALB_SG_ID \
    --protocol tcp \
    --port 80 \
    --cidr 0.0.0.0/0 \
    --region $AWS_REGION 2>/dev/null || true

aws ec2 authorize-security-group-ingress \
    --group-id $ALB_SG_ID \
    --protocol tcp \
    --port 443 \
    --cidr 0.0.0.0/0 \
    --region $AWS_REGION 2>/dev/null || true

# Step 7: Create security group for ECS tasks
echo "🔒 Creating security group for ECS tasks..."
ECS_SG_ID=$(aws ec2 create-security-group \
    --group-name amygdala-ecs-sg \
    --description "Security group for Amygdala ECS tasks" \
    --vpc-id $VPC_ID \
    --query "GroupId" \
    --output text \
    --region $AWS_REGION 2>/dev/null || \
    aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=amygdala-ecs-sg" \
    --query "SecurityGroups[0].GroupId" \
    --output text \
    --region $AWS_REGION)

# Allow traffic from ALB to ECS tasks on port 8000
aws ec2 authorize-security-group-ingress \
    --group-id $ECS_SG_ID \
    --protocol tcp \
    --port 8000 \
    --source-group $ALB_SG_ID \
    --region $AWS_REGION 2>/dev/null || true

# Step 8: Create Application Load Balancer
echo "⚖️ Creating Application Load Balancer..."
ALB_ARN=$(aws elbv2 create-load-balancer \
    --name amygdala-alb \
    --subnets $SUBNET_IDS \
    --security-groups $ALB_SG_ID \
    --scheme internet-facing \
    --type application \
    --ip-address-type ipv4 \
    --query "LoadBalancers[0].LoadBalancerArn" \
    --output text \
    --region $AWS_REGION 2>/dev/null || \
    aws elbv2 describe-load-balancers \
    --names amygdala-alb \
    --query "LoadBalancers[0].LoadBalancerArn" \
    --output text \
    --region $AWS_REGION)

# Step 9: Create target group
echo "🎯 Creating target group..."
TARGET_GROUP_ARN=$(aws elbv2 create-target-group \
    --name amygdala-tg \
    --protocol HTTP \
    --port 8000 \
    --vpc-id $VPC_ID \
    --target-type ip \
    --health-check-path "/healthz" \
    --health-check-interval-seconds 30 \
    --health-check-timeout-seconds 5 \
    --healthy-threshold-count 2 \
    --unhealthy-threshold-count 3 \
    --query "TargetGroups[0].TargetGroupArn" \
    --output text \
    --region $AWS_REGION 2>/dev/null || \
    aws elbv2 describe-target-groups \
    --names amygdala-tg \
    --query "TargetGroups[0].TargetGroupArn" \
    --output text \
    --region $AWS_REGION)

# Step 10: Create ALB listener
echo "👂 Creating ALB listener..."
aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTP \
    --port 80 \
    --default-actions Type=forward,TargetGroupArn=$TARGET_GROUP_ARN \
    --region $AWS_REGION 2>/dev/null || echo "✅ Listener already exists"

# Get ALB DNS name
ALB_DNS=$(aws elbv2 describe-load-balancers \
    --load-balancer-arns $ALB_ARN \
    --query "LoadBalancers[0].DNSName" \
    --output text \
    --region $AWS_REGION)

# Save configuration for deployment script
cat > aws-config.env << EOF
AWS_REGION=$AWS_REGION
CLUSTER_NAME=$CLUSTER_NAME
SERVICE_NAME=$SERVICE_NAME
TASK_FAMILY=$TASK_FAMILY
ECR_REPOSITORY=$ECR_REPOSITORY
VPC_ID=$VPC_ID
ECS_SG_ID=$ECS_SG_ID
TARGET_GROUP_ARN=$TARGET_GROUP_ARN
ALB_DNS=$ALB_DNS
SUBNET_IDS="$SUBNET_IDS"
EOF

echo "✅ AWS infrastructure setup complete!"
echo "🌐 Load Balancer DNS: $ALB_DNS"
echo "📝 Configuration saved to aws-config.env"
echo ""
echo "Next steps:"
echo "1. Store your secrets in AWS Parameter Store"
echo "2. Build and push your Docker image"
echo "3. Deploy your ECS service"
