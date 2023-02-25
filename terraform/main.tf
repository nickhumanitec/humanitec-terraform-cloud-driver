provider "aws" {
  default_tags {
    tags = {
      Humanitec = "true"
    }
  }
}
variable "name" {
  default = "humanitec-tfc-driver"
}

output "url" {
  value = aws_lambda_function_url.l.function_url
}
resource "aws_lambda_function_url" "l" {
  function_name      = aws_lambda_function.l.function_name
  authorization_type = "NONE"
  # qualifier          = "$LATEST"
  cors {
    allow_origins = ["*"]
  }
}

resource "aws_lambda_function" "l" {
  depends_on = [
    aws_cloudwatch_log_group.lg
  ]

  architectures = ["x86_64"]
  function_name = var.name
  role          = aws_iam_role.r.arn
  handler       = "main.lambda_handler"
  runtime       = "python3.9"

  source_code_hash = filebase64sha256("${path.module}/../src/source.zip")
  filename         = "${path.module}/../src/source.zip"

  timeout = 180
  publish = true
  environment {
  }
}

resource "aws_iam_role" "r" {
  name = var.name
  assume_role_policy = jsonencode(
    {
      "Version" : "2012-10-17",
      "Statement" : [
        {
          "Effect" : "Allow",
          "Principal" : {
            "Service" : "lambda.amazonaws.com"
          },
          "Action" : "sts:AssumeRole"
        }
      ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "adefault" {
  role       = aws_iam_role.r.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_cloudwatch_log_group" "lg" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = 14
}
