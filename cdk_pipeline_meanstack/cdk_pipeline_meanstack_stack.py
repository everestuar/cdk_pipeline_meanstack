from aws_cdk import (
    core as cdk
    # aws_sqs as sqs,
)
from aws_cdk import core
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_codebuild as codebuild
import aws_cdk.aws_codepipeline as codepipeline
import aws_cdk.aws_codepipeline_actions as codepipeline_actions
import aws_cdk.aws_iam as iam
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_ecs_patterns as ecs_patterns
import aws_cdk.aws_ecr as ecr

class CdkPipelineMeanstackStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, parms=dict, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Reference to existing ECS Cluster and its configuration
        
        my_vpc = ec2.Vpc.from_lookup(self, "vpc"+parms['stage'],vpc_id = parms['vpc_id'], is_default = parms["vpc_default"])

        # my_security_group = ec2.SecurityGroup.from_security_group_id(self, parms["sg_id"]+parms["stage"], parms["sg_id"])

        # ecs_cluster = ecs.Cluster.from_cluster_attributes(self, parms["ecs_cluster_name"],
        #     cluster_name=parms["ecs_cluster_name"],
        #     security_groups=[my_security_group],
        #     vpc=my_vpc,
        # )

        # ecs_service = ecs.FargateService.from_fargate_service_attributes(self, parms["ecs_fargate_service"],
        #     cluster=ecs_cluster,
        #     service_name=parms["ecs_fargate_service"]
        # )        

        ## Reference to existing ECR Repo
        ecr_repo = ecr.Repository.from_repository_attributes(self, parms["ecr_repo_name"],
            repository_name = parms["ecr_repo_name"],
            repository_arn = parms["ecr_repo_arn"]
        )

        ecs_cluster = ecs.Cluster(self, parms["ecs_cluster_name"], 
            cluster_name = parms["ecs_cluster_name"],
            vpc = my_vpc
        )

        logging = ecs.AwsLogDriver.aws_logs(stream_prefix=parms["ecs_cluster_name"])

        task_role = iam.Role(self, "ecs-task-role-"+self.stack_name,
            role_name="cdk-ecs-task-role-"+self.stack_name,
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )

        execution_role_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            resources=["*"],
            actions=[
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ]
        )

        task_definition = ecs.FargateTaskDefinition(self, "ecs-task-def",             
            task_role=task_role
        )

        task_definition.add_to_execution_role_policy(execution_role_policy)

        container = task_definition.add_container("mean-stack-front-end",
            image=ecs.ContainerImage.from_ecr_repository(ecr_repo),
            memory_limit_mib=512,
            cpu=256,
            logging=logging
        )

        container.add_port_mappings(ecs.PortMapping(
                container_port=4200,
                protocol=ecs.Protocol.TCP
            )
        )

        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(self, parms["ecs_fargate_service"],
            cluster = ecs_cluster,
            task_definition = task_definition,
            public_load_balancer = True,
            desired_count = 1,
            listener_port = 80,
            min_healthy_percent = 100,
            max_healthy_percent = 200,
            assign_public_ip = False,
            task_subnets = ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE),
            # vpc = my_vpc
        )

        autoscaling = fargate_service.service.auto_scale_task_count(
            max_capacity = 4
        )

        autoscaling.scale_on_cpu_utilization("autoscale-policy",
            target_utilization_percent = 80,
            scale_in_cooldown = cdk.Duration.seconds(180),
            scale_out_cooldown = cdk.Duration.seconds(300)
        )



        # Github Repo
        gitHubSource = codebuild.Source.git_hub(
            owner=parms["repo_owner"],
            repo=parms["repo_name"],
            branch_or_ref=parms["repo_branch"],
            clone_depth=1,
            webhook=False,                        
        )

        # Buildspec for codebuild project
        buildspec = {
            "version": "0.2",
            "phases": {
                "pre_build": {
                    "commands": [
                        'env',
                        'aws --version',
                        'docker login -u $dockerhub_username -p $dockerhub_password',
                        'COMMIT_HASH=$(echo $CODEBUILD_RESOLVED_SOURCE_VERSION | cut -c 1-7)',
                        'IMAGE_TAG=${COMMIT_HASH:=latest}',
                        'env'
                    ]
                },
                "build": {                
                    "commands": [
                        'echo "In Build Stage"', 
                        'echo Build started on `date`',
                        'docker build . -t $ECR_REPO_URI:latest',
                        'docker tag $ECR_REPO_URI:latest $ECR_REPO_URI:$IMAGE_TAG',
                        'echo Build completed on `date`'
                    ]
                },
                "post_build": {
                    "commands": [
                        'echo "In Post-Build Stage"',
                        'echo Post-Build started on `date`',
                        'docker login -u AWS -p $(aws ecr get-login-password --region $AWS_REGION) $ECR_REPO_URI',
                        'docker push $ECR_REPO_URI:latest',
                        'docker push $ECR_REPO_URI:$IMAGE_TAG',
                        "printf '[{\"name\":\"mean-stack-front-end\", \"imageUri\":\"%s:%s\"}]' $ECR_REPO_URI $IMAGE_TAG > imagedefinitions.json",
                        "pwd; ls -al; cat imagedefinitions.json",
                        "echo Post-Build completed on `date`"
                    ]
                }
            },
            "artifacts" : {
                "files": [
                    'Angular6/imagedefinitions.json'
                ]
            }
        }

        # Codebuild Project
        build_project = codebuild.Project(self, parms["ecs_cluster_name"] + parms["stage"] + "-bp",
            project_name=parms["ecs_cluster_name"]+parms["stage"]+"bp",
            source=gitHubSource,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_5_0,
                privileged=True
            ),
            environment_variables=(
                {
                    'ECR_REPO_URI': codebuild.BuildEnvironmentVariable(value=parms["ecr_repo_uri"]),
                    'ECS_CLUSTER_NAME': codebuild.BuildEnvironmentVariable(value=parms["ecs_cluster_name"]),
                    'dockerhub_username': codebuild.BuildEnvironmentVariable(value=parms["dockerhub_username"], 
                        type=codebuild.BuildEnvironmentVariableType(value='SECRETS_MANAGER')),
                    'dockerhub_password': codebuild.BuildEnvironmentVariable(value=parms["dockerhub_password"], 
                        type=codebuild.BuildEnvironmentVariableType(value='SECRETS_MANAGER'))
                }
            ),
            # build_spec=codebuild.BuildSpec.from_object(buildspec)
            build_spec=codebuild.BuildSpec.from_source_filename('Angular6/buildspec.yml')            
        )

        # Codepipeline Actions
        source_output = codepipeline.Artifact()
        build_output = codepipeline.Artifact()

        source_action = codepipeline_actions.GitHubSourceAction(
            action_name='GitHub_Source',
            owner=parms["repo_owner"],
            repo=parms["repo_name"],
            branch=parms["repo_branch"],
            oauth_token=cdk.SecretValue.secrets_manager(parms["github_token"]),
            output=source_output
        )

        build_action = codepipeline_actions.CodeBuildAction(
            action_name='CodeBuild',
            project=build_project,
            input=source_output,
            outputs=[build_output]
        )

        deploy_action = codepipeline_actions.EcsDeployAction(
            action_name='DeployAction',
            service=fargate_service,
            image_file=codepipeline.ArtifactPath(build_output, 'Angular6/imagedefinitions.json')
        )

        # Codepipeline
        pipeline = codepipeline.Pipeline(self, "CodePipeline",
            pipeline_name=parms["pipeline_name"],
            stages=[
                codepipeline.StageProps(stage_name="Source", actions=[source_action]),
                codepipeline.StageProps(stage_name="Build", actions=[build_action]),
                codepipeline.StageProps(stage_name="Deploy-to-ECS", actions=[deploy_action])
            ]
        )

        # IAM extra policies to codebuild
        build_project.add_to_role_policy(iam.PolicyStatement(
                actions=["codestar-connections:UseConnection"],
                resources=["*"]
            )
        )

        build_project.add_to_role_policy(iam.PolicyStatement(
                actions=["ecr:*", "ecs:*"],
                resources=["*"]
            )
        )

        build_project.add_to_role_policy(iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=["*"]
            )
        )
