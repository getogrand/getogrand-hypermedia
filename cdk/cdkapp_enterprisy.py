from aws_cdk import (
    App,
    Stack,
    Environment,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_efs as efs,
    aws_elasticloadbalancingv2 as elb,
    aws_codedeploy as codedeploy,
    aws_codepipeline as pipeline,
    aws_codepipeline_actions as pipeline_actions,
    aws_codebuild as codebuild,
)
from constructs import Construct
from typing import Sequence, Mapping, Callable
from jsii import JSIIAbstractClass
from abc import abstractmethod


class BlueGreenDeployment(Construct, metaclass=JSIIAbstractClass):
    @property
    @abstractmethod
    def deploy_group(self) -> codedeploy.EcsDeploymentGroup: ...


class SimpleNlbBlueGreenDeployment(BlueGreenDeployment):
    def __init__(
        self,
        scope: Construct,
        id: str,
        port: int,
        vpc: ec2.IVpc,
        service: ecs.FargateService,
    ):
        super().__init__(scope=scope, id=id)
        self.vpc = vpc
        self.service = service
        self.load_balancer = elb.NetworkLoadBalancer(
            scope=self,
            id="Elb",
            vpc=self.vpc,
            internet_facing=False,
        )
        self.blue_target_group = elb.NetworkTargetGroup(
            scope=self,
            id="BlueTargetGroup",
            target_type=elb.TargetType.IP,
            port=port,
            protocol=elb.Protocol.TCP,
            vpc=self.vpc,
        )
        self.green_target_group = elb.NetworkTargetGroup(
            scope=self,
            id="GreenTargetGroup",
            target_type=elb.TargetType.IP,
            port=port,
            protocol=elb.Protocol.TCP,
            vpc=self.vpc,
        )
        self.listener = self.load_balancer.add_listener(
            id="Listener",
            port=port,
            default_target_groups=[self.blue_target_group],
        )
        self.service.attach_to_network_target_group(self.blue_target_group)
        self.deploy_app = codedeploy.EcsApplication(scope=self, id="CodedeployApp")
        self._deploy_group = codedeploy.EcsDeploymentGroup(
            scope=self,
            id="CodedeployGroup",
            blue_green_deployment_config=codedeploy.EcsBlueGreenDeploymentConfig(
                blue_target_group=self.blue_target_group,
                green_target_group=self.green_target_group,
                listener=self.listener,
            ),
            service=self.service,
            application=self.deploy_app,
        )

    @property
    def deploy_group(self) -> codedeploy.EcsDeploymentGroup:
        return self._deploy_group


class ProxyServiceBlueGreenDeployment(BlueGreenDeployment):
    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.IVpc,
        service: ecs.FargateService,
    ) -> None:
        super().__init__(scope, id)
        self.vpc = vpc
        self.service = service
        self.load_balancer = elb.ApplicationLoadBalancer(
            scope=self, id="Elb", vpc=self.vpc, internet_facing=True
        )

        self.blue_target_group = elb.ApplicationTargetGroup(
            scope=self,
            id="HttpBlueTargetGroup",
            target_type=elb.TargetType.IP,
            port=8000,
            protocol=elb.ApplicationProtocol.HTTP,
            health_check=elb.HealthCheck(path="/health"),
            vpc=self.vpc,
        )
        self.green_target_group = elb.ApplicationTargetGroup(
            scope=self,
            id="HttpGreenTargetGroup",
            target_type=elb.TargetType.IP,
            port=8000,
            protocol=elb.ApplicationProtocol.HTTP,
            health_check=elb.HealthCheck(path="/health"),
            vpc=self.vpc,
        )
        self.listener = self.load_balancer.add_listener(
            id="Http",
            default_target_groups=[self.blue_target_group],
            open=True,
            port=80,
            protocol=elb.ApplicationProtocol.HTTP,
        )
        self.service.attach_to_application_target_group(self.blue_target_group)

        self.deploy_app = codedeploy.EcsApplication(scope=self, id="CodedeployApp")
        self._deploy_group = codedeploy.EcsDeploymentGroup(
            scope=self,
            id="Http",
            blue_green_deployment_config=codedeploy.EcsBlueGreenDeploymentConfig(
                blue_target_group=self.blue_target_group,
                green_target_group=self.green_target_group,
                listener=self.listener,
            ),
            service=self.service,
            application=self.deploy_app,
        )

    @property
    def deploy_group(self) -> codedeploy.EcsDeploymentGroup:
        return self._deploy_group


class Service(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: ecs.ICluster,
        task_exec_role: iam.Role,
        task_role: iam.Role,
        img_repo_suffix: str,
        exposing_port: int,
        container_health_check: ecs.HealthCheck,
        file_system: efs.FileSystem | None = None,
        task_volumes: Sequence[ecs.Volume] | None = None,
        container_port_mappings: Sequence[ecs.PortMapping] | None = None,
        secrets: Mapping[str, ecs.Secret] | None = None,
        environment: Mapping[str, str] | None = None,
        working_directory: str | None = None,
        command: Sequence[str] | None = None,
        mount_points: Sequence[ecs.MountPoint] | None = None,
        discovery_name: str | None = None,
        blue_green_deployment: Callable[
            [ec2.IVpc, ecs.FargateService], BlueGreenDeployment
        ]
        | None = None,
    ):
        super().__init__(scope, id)
        self.cluster = cluster
        self.vpc = self.cluster.vpc
        self.task_def = ecs.FargateTaskDefinition(
            scope=self,
            id="TaskDef",
            cpu=256,
            memory_limit_mib=512,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.X86_64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
            execution_role=task_exec_role,  # type: ignore
            task_role=task_role,  # type: ignore
            volumes=task_volumes,
        )
        self.img_repo = ecr.Repository.from_repository_arn(
            scope=self,
            id="ImageRepo",
            repository_arn=f"arn:aws:ecr:ap-northeast-2:730335367003:repository/{img_repo_suffix}",
        )
        self.container = self.task_def.add_container(
            id="Container",
            image=ecs.ContainerImage.from_ecr_repository(self.img_repo),
            health_check=container_health_check,
            logging=ecs.LogDrivers.aws_logs(stream_prefix="ecs"),
            memory_limit_mib=512,
            port_mappings=container_port_mappings,
            secrets=secrets,
            environment=environment,
            working_directory=working_directory,
            command=command,
        )
        if mount_points:
            self.container.add_mount_points(*mount_points)

        self.service = ecs.FargateService(
            scope=self,
            id="Service",
            task_definition=self.task_def,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            cluster=cluster,
            deployment_controller=ecs.DeploymentController(
                type=ecs.DeploymentControllerType.CODE_DEPLOY
            ),
            desired_count=1,
            enable_execute_command=True,
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(capacity_provider="FARGATE_SPOT", weight=1)
            ],
        )
        # 서비스 삭제가 클러스터 삭제 전에 이루어지도록 설정
        self.service.node.add_dependency(cluster)

        if discovery_name and exposing_port:
            self.service.enable_cloud_map(
                container_port=exposing_port, name=discovery_name
            )
        self.service.connections.allow_from(
            ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            ec2.Port(
                protocol=ec2.Protocol.TCP,
                string_representation=f"{exposing_port}",
                from_port=exposing_port,
                to_port=exposing_port,
            ),
        )
        if file_system:
            file_system.connections.allow_from(self.service.connections, ec2.Port.NFS)

        if blue_green_deployment:
            self.blue_green_deployment = blue_green_deployment(self.vpc, self.service)
        else:
            self.blue_green_deployment = SimpleNlbBlueGreenDeployment(
                scope=self,
                id="BlueGreenDeployment",
                port=exposing_port,
                vpc=self.vpc,
                service=self.service,
            )

        gen_code_deploy_json_proj = codebuild.Project(
            scope=self,
            id="CodeBuildProject",
            build_spec=codebuild.BuildSpec.from_object(
                {
                    "version": "0.2",
                    "phases": {
                        "build": {
                            "commands": [
                                r"""
aws ecs describe-task-definition \
--task-definition $TASK_DEFINITION_ARN \
| jq '.["taskDefinition"] | del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .placementConstraints, .compatibilities, .registeredAt, .registeredBy)' \
> taskdef.json""",
                                r"""
aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME \
| jq '.services[0] | { version: 0.0, Resources: [ { TargetService: { Type: "AWS::ECS::Service", Properties: { TaskDefinition: .taskDefinition, LoadBalancerInfo: { ContainerName: .loadBalancers[0].containerName, ContainerPort: .loadBalancers[0].containerPort } } } } ] }' \
> appspec.json""",
                            ]
                        },
                    },
                    "artifacts": {"files": ["taskdef.json", "appspec.json"]},
                }
            ),
            environment_variables={
                "CLUSTER_NAME": codebuild.BuildEnvironmentVariable(
                    value=self.cluster.cluster_name
                ),
                "SERVICE_NAME": codebuild.BuildEnvironmentVariable(
                    value=self.service.service_name
                ),
                "TASK_DEFINITION_ARN": codebuild.BuildEnvironmentVariable(
                    value=self.task_def.task_definition_arn
                ),
            },
        )
        assert gen_code_deploy_json_proj.role is not None
        gen_code_deploy_json_proj.role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ecs:DescribeTaskDefinition"],
                resources=["*"],
            )
        )
        gen_code_deploy_json_proj.role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ecs:DescribeServices"],
                resources=[self.service.service_arn],
            )
        )

        ecr_change_output = pipeline.Artifact()
        gen_code_deploy_jsons_output = pipeline.Artifact()
        deploy_role = iam.Role(
            scope=self,
            id="DeployRole",
            assumed_by=iam.ServicePrincipal("codepipeline.amazonaws.com"),  # type: ignore
        )
        assert deploy_role.assume_role_policy is not None
        deploy_role.assume_role_policy.add_statements(
            iam.PolicyStatement(
                actions=["sts:AssumeRole"],
                principals=[iam.ServicePrincipal("codebuild.amazonaws.com")],  # type: ignore
            )
        )
        self.build_pipe = pipeline.Pipeline(
            scope=self,
            id="Deploy",
            role=deploy_role,
            pipeline_type=pipeline.PipelineType.V2,
            stages=[
                pipeline.StageProps(
                    stage_name="Source",
                    actions=[
                        pipeline_actions.EcrSourceAction(
                            action_name="EcrChangeDetected",
                            output=ecr_change_output,
                            repository=self.img_repo,
                            role=deploy_role,  # type: ignore
                        )
                    ],
                ),
                pipeline.StageProps(
                    stage_name="Build",
                    actions=[
                        pipeline_actions.CodeBuildAction(
                            action_name="GenerateCodeDeployJsons",
                            input=ecr_change_output,
                            project=gen_code_deploy_json_proj,  # type: ignore
                            outputs=[gen_code_deploy_jsons_output],
                            role=deploy_role,  # type: ignore
                        ),
                    ],
                ),
                pipeline.StageProps(
                    stage_name="Deploy",
                    actions=[
                        pipeline_actions.CodeDeployEcsDeployAction(
                            action_name="Deploy",
                            deployment_group=self.blue_green_deployment.deploy_group,
                            task_definition_template_file=gen_code_deploy_jsons_output.at_path(
                                "taskdef.json"
                            ),
                            app_spec_template_file=gen_code_deploy_jsons_output.at_path(
                                "appspec.json"
                            ),
                            role=deploy_role,  # type: ignore
                        )
                    ],
                ),
            ],
        )


class DbService(Service):
    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: ecs.ICluster,
        task_exec_role: iam.Role,
        task_role: iam.Role,
        file_system: efs.FileSystem,
        secret: secretsmanager.ISecret,
    ):
        super().__init__(
            scope=scope,
            id=id,
            cluster=cluster,
            task_exec_role=task_exec_role,
            task_role=task_role,
            img_repo_suffix="getogrand-hypermedia/db",
            exposing_port=5432,
            container_health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "pg_isready -U postgres"]
            ),
            file_system=file_system,
            task_volumes=[
                ecs.Volume(
                    name="db-volume",
                    efs_volume_configuration=ecs.EfsVolumeConfiguration(
                        file_system_id=file_system.file_system_id
                    ),
                )
            ],
            container_port_mappings=[
                ecs.PortMapping(
                    container_port=5432, host_port=5432, protocol=ecs.Protocol.TCP
                )
            ],
            secrets={
                "POSTGRES_PASSWORD": ecs.Secret.from_secrets_manager(
                    secret=secret, field="db-password"
                )
            },
            mount_points=[
                ecs.MountPoint(
                    container_path="/var/lib/postgresql/data",
                    read_only=False,
                    source_volume="db-volume",
                )
            ],
            discovery_name="db",
        )


class AppService(Service):
    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: ecs.ICluster,
        task_exec_role: iam.Role,
        task_role: iam.Role,
        secret: secretsmanager.ISecret,
    ):
        super().__init__(
            scope=scope,
            id=id,
            cluster=cluster,
            task_exec_role=task_exec_role,
            task_role=task_role,
            img_repo_suffix="getogrand-hypermedia/app",
            exposing_port=8000,
            container_health_check=ecs.HealthCheck(
                command=[
                    "CMD-SHELL",
                    "wget --quiet --spider http://localhost:8000/health",
                ]
            ),
            container_port_mappings=[
                ecs.PortMapping(
                    container_port=8000, host_port=8000, protocol=ecs.Protocol.TCP
                )
            ],
            secrets={
                "SECRET_KEY": ecs.Secret.from_secrets_manager(
                    secret=secret, field="django-secret-key"
                ),
                "DB_PASSWORD": ecs.Secret.from_secrets_manager(
                    secret=secret, field="db-password"
                ),
            },
            environment={"DEBUG": "False", "DB_HOST": "db.getogrand.media"},
            working_directory="/app",
            command=[
                "sh",
                "-c",
                "python manage.py collectstatic --no-input && python manage.py migrate && gunicorn -b 0.0.0.0:8000 --access-logfile '-' getogrand_hypermedia.wsgi",
            ],
            discovery_name="app",
        )


class ProxyService(Service):
    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: ecs.ICluster,
        task_exec_role: iam.Role,
        task_role: iam.Role,
        file_system: efs.FileSystem,
    ):
        super().__init__(
            scope=scope,
            id=id,
            cluster=cluster,
            task_exec_role=task_exec_role,
            task_role=task_role,
            img_repo_suffix="getogrand-hypermedia/proxy",
            exposing_port=443,
            container_health_check=ecs.HealthCheck(
                command=[
                    "CMD-SHELL",
                    "wget --quiet --spider http://localhost:8000/health",
                ]
            ),
            file_system=file_system,
            task_volumes=[
                ecs.Volume(
                    name="proxy-data",
                    efs_volume_configuration=ecs.EfsVolumeConfiguration(
                        file_system_id=file_system.file_system_id
                    ),
                ),
                ecs.Volume(
                    name="proxy-config",
                    efs_volume_configuration=ecs.EfsVolumeConfiguration(
                        file_system_id=file_system.file_system_id
                    ),
                ),
            ],
            container_port_mappings=[
                ecs.PortMapping(
                    container_port=8000, host_port=8000, protocol=ecs.Protocol.TCP
                ),
            ],
            mount_points=[
                ecs.MountPoint(
                    container_path="/data",
                    read_only=False,
                    source_volume="proxy-data",
                ),
                ecs.MountPoint(
                    container_path="/config",
                    read_only=False,
                    source_volume="proxy-config",
                ),
            ],
            blue_green_deployment=lambda vpc, service: ProxyServiceBlueGreenDeployment(
                scope=self, id="BlueGreenDeployment", vpc=vpc, service=service
            ),
        )


class HypermediaStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.vpc = ec2.Vpc(
            scope=self,
            id="Vpc",
            create_internet_gateway=True,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            gateway_endpoints={
                "s3": ec2.GatewayVpcEndpointOptions(
                    service=ec2.GatewayVpcEndpointAwsService.S3
                )
            },
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public", subnet_type=ec2.SubnetType.PUBLIC
                ),
                ec2.SubnetConfiguration(
                    name="private", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
                ),
            ],
        )

        self.vpc.add_interface_endpoint(
            id="EndpointECR", service=ec2.InterfaceVpcEndpointAwsService.ECR
        )
        self.vpc.add_interface_endpoint(
            id="EndpointECRDKR", service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER
        )
        self.vpc.add_interface_endpoint(
            id="EndpointSsmMessages",
            service=ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES,
        )
        self.vpc.add_interface_endpoint(
            id="EndpointLogs",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
        )
        self.vpc.add_interface_endpoint(
            id="EndpointSecretsManager",
            service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
        )
        self.vpc.add_interface_endpoint(
            id="EndpointLoadBalancing",
            service=ec2.InterfaceVpcEndpointAwsService.ELASTIC_LOAD_BALANCING,
        )
        self.vpc.add_interface_endpoint(
            id="EndpointCodeDeploy",
            service=ec2.InterfaceVpcEndpointAwsService.CODEDEPLOY,
        )
        cluster = ecs.Cluster(
            scope=self,
            id="EcsCluster",
            container_insights=True,
            default_cloud_map_namespace=ecs.CloudMapNamespaceOptions(
                name="getogrand.media"
            ),
            enable_fargate_capacity_providers=True,
            execute_command_configuration=ecs.ExecuteCommandConfiguration(),
            vpc=self.vpc,
        )
        cluster.add_default_capacity_provider_strategy(
            [ecs.CapacityProviderStrategy(capacity_provider="FARGATE_SPOT", weight=1)]
        )
        file_system = efs.FileSystem(scope=self, id="Efs", vpc=self.vpc)
        task_role_policy = iam.Policy(
            scope=self,
            id="EcsTaskRolePolicy",
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "ecs:DeregisterContainerInstance",
                            "ecs:DiscoverPollEndpoint",
                            "ecs:Poll",
                            "ecs:RegisterContainerInstance",
                            "ecs:StartTelemetrySession",
                            "ecs:UpdateContainerInstancesState",
                            "ecs:Submit*",
                            "ecr:GetAuthorizationToken",
                            "ecr:BatchCheckLayerAvailability",
                            "ecr:GetDownloadUrlForLayer",
                            "ecr:BatchGetImage",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                            "logs:CreateLogGroup",
                            "ssmmessages:CreateControlChannel",
                            "ssmmessages:CreateDataChannel",
                            "ssmmessages:OpenControlChannel",
                            "ssmmessages:OpenDataChannel",
                        ],
                        resources=["*"],
                    )
                ]
            ),
        )
        task_role = iam.Role(
            scope=self,
            id="EcsTaskRole",
            assumed_by=iam.ServicePrincipal(service="ecs-tasks.amazonaws.com"),  # type: ignore
        )
        task_role_policy.attach_to_role(task_role)  # type: ignore
        secret = secretsmanager.Secret.from_secret_complete_arn(
            scope=self,
            id="Secret",
            secret_complete_arn="arn:aws:secretsmanager:ap-northeast-2:730335367003:secret:getogrand-hypermedia-ImNX6Q",
        )
        task_exec_role_policy = iam.Policy(
            scope=self,
            id="EcsTaskExecRolePolicy",
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "ecr:GetAuthorizationToken",
                            "ecr:BatchCheckLayerAvailability",
                            "ecr:GetDownloadUrlForLayer",
                            "ecr:BatchGetImage",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                            "logs:CreateLogGroup",
                        ],
                        resources=["*"],
                    ),
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["secretsmanager:GetSecretValue"],
                        resources=[secret.secret_arn],
                    ),
                ]
            ),
        )
        task_exec_role = iam.Role(
            scope=self,
            id="EcsTaskExecRole",
            assumed_by=iam.ServicePrincipal(service="ecs-tasks.amazonaws.com"),  # type: ignore
        )
        task_exec_role_policy.attach_to_role(task_exec_role)  # type: ignore

        self.db_service = DbService(
            scope=self,
            id="DbService",
            cluster=cluster,
            task_exec_role=task_exec_role,
            task_role=task_role,
            file_system=file_system,
            secret=secret,
        )
        self.app_service = AppService(
            scope=self,
            id="AppService",
            cluster=cluster,
            task_exec_role=task_exec_role,
            task_role=task_role,
            secret=secret,
        )
        self.proxy_service = ProxyService(
            scope=self,
            id="ProxyService",
            cluster=cluster,
            task_exec_role=task_exec_role,
            task_role=task_role,
            file_system=file_system,
        )


app = App()
HypermediaStack(
    app,
    "GetograndHypermedia",
    env=Environment(account="730335367003", region="ap-northeast-2"),
)
app.synth()
