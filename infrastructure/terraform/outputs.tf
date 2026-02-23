output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.postgres.address
  sensitive   = true
}

output "rds_port" {
  description = "RDS port"
  value       = aws_db_instance.postgres.port
}

output "lambda_function_name" {
  description = "Pipeline Lambda function name"
  value       = aws_lambda_function.pipeline.function_name
}

output "lambda_function_arn" {
  description = "Pipeline Lambda ARN"
  value       = aws_lambda_function.pipeline.arn
}

output "db_secret_arn" {
  description = "Secrets Manager ARN storing DATABASE_URL"
  value       = aws_secretsmanager_secret.db_url.arn
}

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}
