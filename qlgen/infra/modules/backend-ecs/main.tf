# --- ECR Repository ---

resource "aws_ecr_repository" "backend" {
  name                 = "${var.project_name}-backend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# --- ECS Cluster ---

resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

# --- CloudWatch Log Group ---

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.project_name}-backend"
  retention_in_days = 14
}

# --- IAM: Task Execution Role (ECR pull + logs + secrets) ---

resource "aws_iam_role" "ecs_execution" {
  name = "${var.project_name}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_default" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "secrets-access"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = [
        var.api_keys_secret_arn,
        var.db_password_secret_arn
      ]
    }]
  })
}

# --- IAM: Task Role (Bedrock access for running container) ---

resource "aws_iam_role" "ecs_task" {
  name = "${var.project_name}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "bedrock_invoke" {
  name = "bedrock-invoke"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:Converse",
        "bedrock:ConverseStream"
      ]
      Resource = [
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4*",
        "arn:aws:bedrock:*:*:inference-profile/us.anthropic.claude-sonnet-4*"
      ]
    }]
  })
}

# --- ALB ---

resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids
  idle_timeout       = 600

  tags = { Name = "${var.project_name}-alb" }
}

resource "aws_lb_target_group" "backend" {
  name        = "${var.project_name}-backend-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/api/v1/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  deregistration_delay = 300
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}

# --- ECS Task Definition ---

resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project_name}-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "backend"
    image = "${aws_ecr_repository.backend.repository_url}:latest"

    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]

    environment = [
      { name = "CORS_ALLOWED_ORIGINS", value = var.cors_allowed_origins },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "BEDROCK_MODEL_ID", value = "us.anthropic.claude-sonnet-4-20250514-v1:0" },
      { name = "DATABASE_URL", value = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${var.db_endpoint}/qlgen" },
      { name = "DATABASE_URL_SYNC", value = "postgresql://${var.db_username}:${var.db_password}@${var.db_endpoint}/qlgen" },
      { name = "APOLLO_BASE_URL", value = "https://api.apollo.io/v1" },
      { name = "EXA_BASE_URL", value = "https://api.exa.ai" },
      { name = "HUNTER_BASE_URL", value = "https://api.hunter.io/v2" },
      { name = "LUSHA_BASE_URL", value = "https://api.lusha.com" },
      { name = "CLAY_BASE_URL", value = "https://api.clay.com" },
      { name = "TAVILY_BASE_URL", value = "https://api.tavily.com" },
    ]

    secrets = [
      { name = "APOLLO_API_KEY", valueFrom = "${var.api_keys_secret_arn}:APOLLO_API_KEY::" },
      { name = "EXA_API_KEY", valueFrom = "${var.api_keys_secret_arn}:EXA_API_KEY::" },
      { name = "HUNTER_API_KEY", valueFrom = "${var.api_keys_secret_arn}:HUNTER_API_KEY::" },
      { name = "LUSHA_API_KEY", valueFrom = "${var.api_keys_secret_arn}:LUSHA_API_KEY::" },
      { name = "TAVILY_API_KEY", valueFrom = "${var.api_keys_secret_arn}:TAVILY_API_KEY::" },
      { name = "CLAY_API_KEY", valueFrom = "${var.api_keys_secret_arn}:CLAY_API_KEY::" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.backend.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

# --- ECS Service ---

resource "aws_ecs_service" "backend" {
  name            = "${var.project_name}-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http]
}
