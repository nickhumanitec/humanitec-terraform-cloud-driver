variable "humanitec_organization" { default = "HUMANITEC_ORGANIZATION" }
variable "humanitec_token" { default = "HUMANITEC_TOKEN" }

terraform {
  required_providers {
    humanitec = {
      source = "humanitec/humanitec"
    }
  }
}

provider "humanitec" {
  org_id = var.humanitec_organization
  token  = var.humanitec_token
}

resource "humanitec_resource_definition" "my-tf-cloud-workload-resource" {
  driver_type = "${var.humanitec_organization}/my-tf-cloud"
  id          = "my-tfc-workload"
  name        = "my-tfc-workload"
  type        = "workload"

  #   criteria = [
  #     {
  #       res_id = null
  #     }
  #   ]

  driver_inputs = {
    secrets = {
      data = jsonencode(
        {
          "tfc_token" : "example.atlasv1.example...",
          "github_token" : "ghp_example...",
          "terraform_secrets" : [
            {
              "key" : "my_secret",
              "value" : "\"my secret\""
            }
          ]
        }
      )
    },
    values = {
      "data" = jsonencode(
        {
          "humanitec" : {
            "org" : "my-humanitec-org",
            "app" : "$${context.app.id}",
            "env" : "$${context.env.id}",
            "res" : "$${context.res.id}"
          },
          "source" : {
            "branch" : "main",
            "path" : "humanitec-aws-examples/dummy/",
            "source_commit" : "https://api.github.com/repos/nickhumanitec/humanitec-aws-examples/commits?sha=main",
            "source_zip" : "https://github.com/nickhumanitec/humanitec-aws-examples/archive/refs/heads/main.zip"
          },
          "terraform_cloud" : {
            "organization_name" : "my-terraform-org"
          },
          "terraform_variables" : [
            {
              "key" : "my_input",
              "value" : "\"plaintext value\""
            },
            {
              "key" : "my_secret",
              "value" : "\"my secret\""
            }
          ]
        }
      )
    }
  }
}
