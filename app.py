#!/usr/bin/env python3
import os
import distutils.util
from aws_cdk import core as cdk
from aws_cdk import core
from cdk_pipeline_meanstack.cdk_pipeline_meanstack_stack import CdkPipelineMeanstackStack

## START of Parameters Definition
parms = {}

parms["stage"] = os.getenv("STAGE", "dev")
parms["vpc_id"] = os.getenv("VPC_ID", "")
parms["vpc_default"] = bool(distutils.util.strtobool(os.getenv("VPC_DEFAULT", 'False')))
parms["sg_id"] = os.getenv("SG_ID", "")
parms["repo_owner"] = os.getenv("REPO_OWNER", "everestuar")
parms["repo_name"] = os.getenv("REPO_NAME", "")
parms["repo_branch"] = os.getenv("REPO_BRANCH", "")
parms["ecr_repo_name"] = os.getenv("ECR_REPO_NAME")
parms["ecr_repo_uri"] = os.getenv("ECR_REPO_URI")
parms["ecr_repo_arn"] = os.getenv("ECR_REPO_ARN")
parms["ecs_cluster_name"] = os.getenv("ECS_CLUSTER_NAME")
parms["ecs_fargate_service"] = os.getenv("ECS_FARGET_SERVICE")
parms["pipeline_name"] = os.getenv("PIPELINE_NAME")
parms["dockerhub_username"] = os.getenv("DOCKERHUB_USERNAME")
parms["dockerhub_password"] = os.getenv("DOCKERHUB_PASSWORD")
parms["github_token"] = os.getenv("GITHUB_TOKEN")

## END of Parameters Definition

env_NV = cdk.Environment(account=os.environ.get("DEPLOY_ACCOUNT", os.environ["DEFAULT_ACCOUNT"]),
    region=os.environ.get("DEPLOY_REGION", os.environ["DEFAULT_REGION"]))

app = core.App()
    # CdkPipelineMeanstackStack(app, "CdkPipelineMeanstackStack",
    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.

    # Uncomment the next line to specialize this stack for the AWS Account
    # and Region that are implied by the current CLI configuration.

    #env=core.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */

    #env=core.Environment(account='123456789012', region='us-east-1'),

    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    #     )

pipeline = CdkPipelineMeanstackStack(app, "Pipeline-"+parms["stage"], env=env_NV, parms=parms)
core.Tags.of(pipeline).add("Env", parms["stage"])

app.synth()
