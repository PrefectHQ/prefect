# Prefect AWS CLI Usage

The `prefect-aws` CLI provides commands to deploy and manage ECS worker infrastructure for Prefect workflows.

## Installation

The CLI is automatically available when you install prefect-aws:

```bash
pip install prefect-aws
```

## Commands

### ECS Worker Commands

All ECS worker commands are under the `prefect-aws ecs-worker` namespace:

#### Deploy Service Stack

Deploy a complete ECS service with worker tasks and event monitoring:

```bash
# Interactive deployment (prompts for required parameters)
prefect-aws ecs-worker deploy-service

# With all parameters specified for Prefect Cloud
prefect-aws ecs-worker deploy-service \
  --work-pool-name my-pool \
  --stack-name my-pool-workers \
  --prefect-api-url https://api.prefect.cloud/api \
  --existing-cluster-identifier my-cluster \
  --existing-vpc-id vpc-12345678 \
  --existing-subnet-ids subnet-12345678,subnet-87654321 \
  --prefect-api-key your-api-key \
  --desired-count 2 \
  --max-capacity 5

# With self-hosted Prefect server (no auth required)
prefect-aws ecs-worker deploy-service \
  --work-pool-name my-pool \
  --stack-name my-pool-workers \
  --prefect-api-url http://localhost:4200/api \
  --existing-cluster-identifier my-cluster \
  --existing-vpc-id vpc-12345678 \
  --existing-subnet-ids subnet-12345678,subnet-87654321 \
  --desired-count 2 \
  --max-capacity 5

# Dry run to see what would be deployed
prefect-aws ecs-worker deploy-service --dry-run
```

#### Deploy Events-Only Stack

Deploy only event monitoring infrastructure for an existing ECS setup:

```bash
# For Prefect Cloud
prefect-aws ecs-worker deploy-events \
  --work-pool-name my-pool \
  --prefect-api-url https://api.prefect.cloud/api \
  --existing-cluster-arn arn:aws:ecs:us-east-1:123456789012:cluster/my-cluster \
  --prefect-api-key your-api-key

# For self-hosted Prefect server  
prefect-aws ecs-worker deploy-events \
  --work-pool-name my-pool \
  --prefect-api-url http://localhost:4200/api \
  --existing-cluster-arn arn:aws:ecs:us-east-1:123456789012:cluster/my-cluster
```

#### List Stacks

List all stacks deployed by the CLI:

```bash
# Table format (default)
prefect-aws ecs-worker list

# JSON format
prefect-aws ecs-worker list --format json
```

#### Check Stack Status

Get detailed status of a specific stack:

```bash
prefect-aws ecs-worker status my-pool-workers
```

#### Delete Stack

Delete a stack deployed by the CLI:

```bash
# With confirmation prompt
prefect-aws ecs-worker delete my-pool-workers

# Force delete without confirmation
prefect-aws ecs-worker delete my-pool-workers --force
```


## Authentication

### Prefect API Authentication

The CLI handles authentication differently based on your Prefect setup:

**Prefect Cloud** (API URL contains `api.prefect.cloud`):
- **API Key is required** - The CLI will prompt for your Prefect Cloud API key if not provided
- You can provide the key via `--prefect-api-key` option or use an existing AWS Secrets Manager secret with `--prefect-api-key-secret-arn`

**Self-hosted Prefect Server**:
- **Authentication is optional** - The CLI will ask if your server requires authentication
- If authentication is needed, provide the auth string via `--prefect-api-key` (despite the name, this accepts any auth string for self-hosted servers)
- If no authentication is required, you can leave the API key fields empty

### Interactive Authentication Flow

When running commands interactively, the CLI will:
1. Prompt for the Prefect API URL (defaults to Prefect Cloud)
2. Detect if you're using Prefect Cloud or self-hosted
3. For Prefect Cloud: Require an API key
4. For self-hosted: Ask if authentication is needed, then optionally prompt for auth string

## AWS Configuration

### Credentials

The CLI uses your AWS credentials configured through:
- AWS credentials file (`~/.aws/credentials`)
- AWS config file (`~/.aws/config`)
- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- IAM roles (if running on EC2)

### Region and Profile

Specify AWS region and profile:

```bash
prefect-aws ecs-worker deploy-service --region us-west-2 --profile production
```

## Required AWS Permissions

Your AWS credentials need the following permissions:

### CloudFormation
- `cloudformation:CreateStack`
- `cloudformation:UpdateStack`
- `cloudformation:DeleteStack`
- `cloudformation:DescribeStacks`
- `cloudformation:ValidateTemplate`
- `cloudformation:GetTemplate`

### ECS
- `ecs:CreateService`
- `ecs:UpdateService`
- `ecs:DeleteService`
- `ecs:DescribeServices`
- `ecs:DescribeClusters`
- `ecs:RegisterTaskDefinition`
- `ecs:DeregisterTaskDefinition`

### IAM
- `iam:CreateRole`
- `iam:DeleteRole`
- `iam:AttachRolePolicy`
- `iam:DetachRolePolicy`
- `iam:PassRole`

### EC2
- `ec2:DescribeVpcs`
- `ec2:DescribeSubnets`
- `ec2:DescribeSecurityGroups`
- `ec2:DescribeNetworkInterfaces`
- `ec2:CreateSecurityGroup`
- `ec2:DeleteSecurityGroup`
- `ec2:AuthorizeSecurityGroupIngress`
- `ec2:AuthorizeSecurityGroupEgress`
- `ec2:RevokeSecurityGroupIngress`
- `ec2:RevokeSecurityGroupEgress`

### SQS
- `sqs:CreateQueue`
- `sqs:DeleteQueue`
- `sqs:GetQueueAttributes`
- `sqs:SetQueueAttributes`
- `sqs:GetQueueUrl`
- `sqs:SendMessage`
- `sqs:ReceiveMessage`
- `sqs:DeleteMessage`

### EventBridge
- `events:PutRule`
- `events:DeleteRule`
- `events:PutTargets`
- `events:RemoveTargets`
- `events:DescribeRule`
- `events:ListTargetsByRule`

### CloudWatch Logs
- `logs:CreateLogGroup`
- `logs:DeleteLogGroup`
- `logs:DescribeLogGroups`
- `logs:PutRetentionPolicy`
- `logs:CreateLogStream`
- `logs:PutLogEvents`
- `logs:GetLogEvents`
- `logs:DescribeLogStreams`

### Secrets Manager
- `secretsmanager:CreateSecret`
- `secretsmanager:DeleteSecret`
- `secretsmanager:DescribeSecret`
- `secretsmanager:GetSecretValue`
- `secretsmanager:PutSecretValue`
- `secretsmanager:UpdateSecret`
- `secretsmanager:TagResource`

### Application Auto Scaling
- `application-autoscaling:RegisterScalableTarget`
- `application-autoscaling:DeregisterScalableTarget`
- `application-autoscaling:PutScalingPolicy`
- `application-autoscaling:DeleteScalingPolicy`
- `application-autoscaling:DescribeScalableTargets`
- `application-autoscaling:DescribeScalingPolicies`

## Stack Management

### CLI-Deployed Stacks Only

The CLI only manages stacks that it has deployed. Stacks are tagged with:
- `ManagedBy: prefect-aws-cli`
- `DeploymentType: ecs-worker`
- `StackType: service|events`
- `WorkPoolName: <work-pool-name>`

This ensures that `list` and `delete` operations only affect CLI-deployed infrastructure.

### Stack Naming

Default stack names follow the pattern:
- Service stacks: `{work-pool-name}-workers`
- Events stacks: `{work-pool-name}-events`

## Examples

### Complete Service Deployment

```bash
prefect-aws ecs-worker deploy-service \
  --work-pool-name production-pool \
  --prefect-api-url https://api.prefect.cloud/api \
  --existing-cluster-identifier production-cluster \
  --existing-vpc-id vpc-abc12345 \
  --existing-subnet-ids subnet-123,subnet-456 \
  --prefect-api-key pfu_your_api_key_here \
  --desired-count 3 \
  --min-capacity 1 \
  --max-capacity 10 \
  --task-cpu 2048 \
  --task-memory 4096
```

### Events-Only for Existing Infrastructure

```bash
prefect-aws ecs-worker deploy-events \
  --work-pool-name existing-pool \
  --prefect-api-url https://api.prefect.cloud/api \
  --existing-cluster-arn arn:aws:ecs:us-east-1:123456789012:cluster/existing \
  --prefect-api-key pfu_your_api_key_here
```

### Managing Multiple Environments

```bash
# Production (Prefect Cloud)
prefect-aws ecs-worker deploy-service \
  --work-pool-name prod-pool \
  --prefect-api-url https://api.prefect.cloud/api \
  --profile production \
  --region us-east-1

# Staging (Self-hosted)
prefect-aws ecs-worker deploy-service \
  --work-pool-name staging-pool \
  --prefect-api-url http://staging.company.com/api \
  --profile staging \
  --region us-west-2

# List stacks in each environment
prefect-aws ecs-worker list --profile production --region us-east-1
prefect-aws ecs-worker list --profile staging --region us-west-2
```