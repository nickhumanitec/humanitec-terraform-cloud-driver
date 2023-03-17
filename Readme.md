# Humanitec reference Terraform Cloud Driver

## Background
This repository contains an unsupported experimental reference implementation for Terraform Cloud, this can used as an starting point with env0, Scalr, Spacelift and the similar services to manage your Infrastructure.

This implementation uses the version 0.9.2 of the API Spec available at [https://docs.humanitec.com/integrations/custom-resource-drivers/driver-api-spec](https://docs.humanitec.com/integrations/custom-resource-drivers/driver-api-spec).
For more information on how to develop a driver, please consult [https://docs.humanitec.com/integrations/custom-resource-drivers](https://docs.humanitec.com/integrations/custom-resource-drivers).
Please contact your Customer Support Engineer representative for the latest version of this driver or its official equivalent.

### Supported Features
* Supports GitHub public and private respositories (with GitHub token)
* Project Upsert
* Workspace Upsert
* Runs: First Run, Reruns (when inputs change), Reruns (when source code changes), Destroy runs
* Empty Workspace Deletion
* Empty Project Deletion

### Terraform Cloud Organization
Each application is scoped to a project, projects are named: `humanitec-{OrgId}-{AppId}` and within them, each resource under a workspace with the following name: `{EnvId}-{ResId}`.

### Architecture
This driver is built in Python 3.9, it runs on Amazon AWS Lambda and can be accessed over the internet using Lambda function URLs. The driver does not permissions other than access to CloudWatch.

# Installation
* To install, you will need an AWS Amazon account with AWS IAM permissions to create a AWS Lambda and an AWS IAM Role.

## Build Driver
_Note: Make sure you build for amd64 (or arm64 if you are on a M1/M2 Mac, do not forget to configure the AWS Lambda runtime accordingly)_
```
cd src/
docker rm tfc_driver_container || true &&
docker build -t tfc_driver . --file=Dockerfile --platform=linux/amd64 &&
docker run --name=tfc_driver_container --platform=linux/amd64 tfc_driver &&
docker cp tfc_driver_container:/source.zip .
```

## Deploy to AWS using Terraform
```
cd terraform/
export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_DEFAULT_REGION=ca-central-1
terraform init
terraform apply
```

## Driver Registration
Please review [manifests/driver_definition.json](manifests/driver_definition.json), you will need to change the `id` of your driver (line 2) `target` (line 53).
```
export HUMANITEC_ORG="my-org"
export HUMANITEC_TOKEN="my-token"
curl -X POST https://api.humanitec.io/orgs/$HUMANITEC_ORG/resources/drivers \
   -H 'Content-Type: application/json' \
   -H "Authorization: Bearer $HUMANITEC_TOKEN" \
   -d @src/driver_definition.json
```

### Input Schema
* General Schema for the UI, all values are required.
  - Values:
    ```
    {
        "humanitec":{
            "org":"my-humanitec-org",
            "app":"${context.app.id}",
            "env":"${context.env.id}",
            "res":"${context.res.id}"
        },
        "source":{
            "branch":"main",
            "path":"humanitec-aws-examples-main/terraform-training/echo",
            "source_commit":"https://api.github.com/repos/nickhumanitec/humanitec-aws-examples/commits?sha=main",
            "source_zip":"https://github.com/nickhumanitec/humanitec-aws-examples/archive/refs/heads/main.zip"
        },
        "terraform_cloud":{
            "organization_name":"my-terraform-org"
        },
        "terraform_variables":[
            {
                "key":"my_input",
                "value":"\"plaintext value\""
            }
        ]
    }
    ```
  - Secrets:
    ```
    {
        "tfc_token":"example.atlasv1.example...",
        "github_token":"ghp_example...",
        "terraform_secrets":[
            {
                "key":"my_secret",
                "value":"\"my secret\""
            }
        ]
    }
    ```
* For Terraform: See [manifests/resource_definition.tf](manifests/resource_definition.tf) for a workload type resource.
* For API: Even though Terraform is recommended, below a skeleton example is provided.
```
curl https://api.humanitec.io/orgs/$HUMANITEC_ORG/resources/defs \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $HUMANITEC_TOKEN" \
  --data-raw '{
   "id":"my-tfc-workload-via-api",
   "name":"my-tfc-workload-via-api",
   "type":"workload",
   "driver_inputs":{
      "values":{
         "data":{

         }
      },
      "secrets":{
         "data":{

         }
      }
   },
   "driver_type":"$HUMANITEC_ORG/my-tf-cloud"
}'
```

### TODO
* Automated and Manual Approvals, with VCS driven workflow vs API (and async API upload)
* Generalize for GitHub enterprise, GitLab and other VCS
* Schema Validation
* Tag workspaces
* Terraform Cloud API Backoff and retry
* Tests

### Caveats and Known Issues
* Workflow and workspace/run configurations have been selected and are not user modifiable.
* Resource deletion can take several minutes after they are replaced or deleted.
* Projects are deleted when there are no more Workspaces within them, otherwise it fails silently.
* Classic GitHub token has been tested, with full control of private repositories.
* Terraform User API token has been tested, it must have all the permissions needed.
* To deploy to AWS or other Cloud Provider, add the credentials within Terraform Cloud as [Variable Sets](https://developer.hashicorp.com/terraform/tutorials/cloud/cloud-multiple-variable-sets).
* Please note that Terraform Variables must be provided with single quotes or similar for other than non integers, as specified in [https://developer.hashicorp.com/terraform/language/values/variables#using-input-variable-values](https://developer.hashicorp.com/terraform/language/values/variables#using-input-variable-values).
* Warning: Enabling logging within the Lambda function will log secrets and sensitive information.
