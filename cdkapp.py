from aws_cdk import (
    App,
    Stack,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_efs as efs,
    aws_elasticloadbalancingv2 as elb,
    aws_codedeploy as codedeploy,
)
from constructs import Construct


class DbService(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: ecs.ICluster,
        task_exec_role: iam.Role,
        task_role: iam.Role,
        file_system: efs.FileSystem,
        secret: secretsmanager.ISecret,
    ) -> None:
        super().__init__(scope, id)
        self.vpc = cluster.vpc
        self.task_def = ecs.FargateTaskDefinition(
            scope=self,
            id="TaskDef",
            cpu=256,
            memory_limit_mib=512,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.X86_64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
            family="GetograndHypermedia",
            execution_role=task_exec_role,  # type: ignore
            task_role=task_role,  # type: ignore
            volumes=[
                ecs.Volume(
                    name="db-volume",
                    efs_volume_configuration=ecs.EfsVolumeConfiguration(
                        file_system_id=file_system.file_system_id
                    ),
                )
            ],
        )
        self.img_repo = ecr.Repository.from_repository_arn(
            scope=self,
            id="ImageRepo",
            repository_arn="arn:aws:ecr:ap-northeast-2:730335367003:repository/getogrand-hypermedia/db",
        )
        self.container = self.task_def.add_container(
            id="Container",
            container_name="getogrand-hypermedia-db",
            image=ecs.ContainerImage.from_ecr_repository(self.img_repo),
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "pg_isready -U postgres"]
            ),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="ecs"),
            memory_limit_mib=512,
            port_mappings=[
                ecs.PortMapping(
                    container_port=5432, host_port=5432, protocol=ecs.Protocol.TCP
                )
            ],
            secrets={
                "POSTGRES_PASSWORD": ecs.Secret.from_secrets_manager(
                    secret=secret, field="db-password"
                )
            },
        )
        self.container.add_mount_points(
            ecs.MountPoint(
                container_path="/var/lib/postgresql/data",
                read_only=False,
                source_volume="db-volume",
            )
        )
        self.service = ecs.FargateService(
            scope=self,
            id="Service",
            service_name="getogrand-hypermedia-db",
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
        self.service.enable_cloud_map(
            container_port=5432,
            name="db",
        )
        self.service.connections.allow_from(
            ec2.Peer.ipv4(self.vpc.vpc_cidr_block), ec2.Port.POSTGRES
        )
        file_system.connections.allow_from(self.service.connections, ec2.Port.NFS)

        self.load_balancer = elb.NetworkLoadBalancer(
            scope=self,
            id="Elb",
            load_balancer_name="getogrand-hypermedia-db",
            vpc=self.vpc,
            internet_facing=False,
        )
        self.blue_target_group = elb.NetworkTargetGroup(
            scope=self,
            id="BlueTargetGroup",
            target_group_name="getogrand-hypermedia-db-blue",
            target_type=elb.TargetType.IP,
            port=5432,
            protocol=elb.Protocol.TCP,
            vpc=self.vpc,
        )
        self.green_target_group = elb.NetworkTargetGroup(
            scope=self,
            id="GreenTargetGroup",
            target_group_name="getogrand-hypermedia-db-green",
            target_type=elb.TargetType.IP,
            port=5432,
            protocol=elb.Protocol.TCP,
            vpc=self.vpc,
        )
        self.listener = self.load_balancer.add_listener(
            id="Listener", port=5432, default_target_groups=[self.blue_target_group]
        )
        self.service.attach_to_network_target_group(self.blue_target_group)
        self.deploy_app = codedeploy.EcsApplication(
            scope=self, id="DbCodedeployApp", application_name="getogrand-hypermedia-db"
        )
        self.deploy_group = codedeploy.EcsDeploymentGroup(
            scope=self,
            id="DbCodedeployGroup",
            deployment_group_name="getogrand-hypermedia-db",
            blue_green_deployment_config=codedeploy.EcsBlueGreenDeploymentConfig(
                blue_target_group=self.blue_target_group,
                green_target_group=self.green_target_group,
                listener=self.listener,
            ),
            service=self.service,
            application=self.deploy_app,
        )


class AppService(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: ecs.ICluster,
        task_exec_role: iam.Role,
        task_role: iam.Role,
        secret: secretsmanager.ISecret,
    ) -> None:
        super().__init__(scope, id)
        self.vpc = cluster.vpc
        self.task_def = ecs.FargateTaskDefinition(
            scope=self,
            id="TaskDef",
            cpu=256,
            memory_limit_mib=512,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.X86_64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
            family="GetograndHypermedia",
            execution_role=task_exec_role,  # type: ignore
            task_role=task_role,  # type: ignore
        )
        self.img_repo = ecr.Repository.from_repository_arn(
            scope=self,
            id="ImageRepo",
            repository_arn="arn:aws:ecr:ap-northeast-2:730335367003:repository/getogrand-hypermedia/app",
        )
        self.container = self.task_def.add_container(
            id="Container",
            container_name="getogrand-hypermedia-app",
            image=ecs.ContainerImage.from_ecr_repository(self.img_repo),
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "wget --quiet --spider http://localhost:8000"]
            ),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="ecs"),
            memory_limit_mib=512,
            port_mappings=[
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
            environment={"DEBUG": "False", "DB_HOST": "db"},
            working_directory="/app",
            command=[
                "daphne",
                "-b",
                "0.0.0.0",
                "-p",
                "8000",
                "getogrand_hypermedia.asgi:application",
            ],
        )
        self.service = ecs.FargateService(
            scope=self,
            id="Service",
            service_name="getogrand-hypermedia-app",
            task_definition=self.task_def,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            cluster=cluster,
            # deployment_controller=
            desired_count=1,
            enable_execute_command=True,
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(capacity_provider="FARGATE_SPOT", weight=1)
            ],
        )
        self.service.enable_cloud_map(
            container_port=8000,
            name="app",
        )
        self.service.connections.allow_from(
            ec2.Peer.ipv4(self.vpc.vpc_cidr_block), ec2.Port.HTTP
        )


class HypermediaStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.vpc = ec2.Vpc(
            scope=self,
            id="Vpc",
            vpc_name="getogrand-hypermedia",
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
            cluster_name="getogrand-hypermedia",
            container_insights=True,
            default_cloud_map_namespace=ecs.CloudMapNamespaceOptions(
                name="getogrand-hypermedia"
            ),
            enable_fargate_capacity_providers=True,
            execute_command_configuration=ecs.ExecuteCommandConfiguration(),
            vpc=self.vpc,
        )
        cluster.add_default_capacity_provider_strategy(
            [ecs.CapacityProviderStrategy(capacity_provider="FARGATE_SPOT", weight=1)]
        )
        file_system = efs.FileSystem(
            scope=self, id="Efs", file_system_name="getogrand-hypermedia", vpc=self.vpc
        )
        task_role_policy = iam.Policy(
            scope=self,
            id="EcsTaskRolePolicy",
            policy_name="getogrand-hypermedia-ecs-task-role",
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
            role_name="getogrand-hypermedia-ecs-task-role",
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
            policy_name="getogrand-hypermedia-ecs-task-exec-role",
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
            role_name="getogrand-hypermedia-ecs-task-exec-role",
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


app = App()
HypermediaStack(app, "GetograndHypermedia")
app.synth()
