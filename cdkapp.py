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
        vpc = cluster.vpc
        task_def = ecs.FargateTaskDefinition(
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
        img_repo = ecr.Repository.from_repository_arn(
            scope=self,
            id="ImageRepo",
            repository_arn="arn:aws:ecr:ap-northeast-2:730335367003:repository/getogrand-hypermedia/db",
        )
        container = task_def.add_container(
            id="Container",
            image=ecs.ContainerImage.from_ecr_repository(img_repo),
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
        container.add_mount_points(
            ecs.MountPoint(
                container_path="/var/lib/postgresql/data",
                read_only=False,
                source_volume="db-volume",
            )
        )
        service = ecs.FargateService(
            scope=self,
            id="Service",
            task_definition=task_def,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            cluster=cluster,
            deployment_controller=ecs.DeploymentController(
                type=ecs.DeploymentControllerType.ECS
            ),
            desired_count=1,
            enable_execute_command=True,
            assign_public_ip=True,
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(capacity_provider="FARGATE_SPOT", weight=1)
            ],
        )
        service.enable_cloud_map(
            container_port=5432,
            name="db",
        )
        service.connections.allow_from(
            ec2.Peer.ipv4(vpc.vpc_cidr_block), ec2.Port.POSTGRES
        )
        file_system.connections.allow_from(service.connections, ec2.Port.NFS)

        # db_lb = elb.NetworkLoadBalancer(
        #     scope=self, id="DbElb", vpc=vpc, internet_facing=False
        # )
        # blue_target_group = elb.NetworkTargetGroup(
        #     scope=self,
        #     id="BlueTargetGroup",
        #     target_type=elb.TargetType.IP,
        #     port=5432,
        #     protocol=elb.Protocol.TCP,
        #     vpc=vpc,
        # )
        # green_target_group = elb.NetworkTargetGroup(
        #     scope=self,
        #     id="GreenTargetGroup",
        #     target_type=elb.TargetType.IP,
        #     port=5432,
        #     protocol=elb.Protocol.TCP,
        #     vpc=vpc,
        # )
        # listener = db_lb.add_listener(
        #     id="Listener", port=5432, default_target_groups=[blue_target_group]
        # )
        # db_service.attach_to_network_target_group(blue_target_group)
        # deploy_app = codedeploy.EcsApplication(scope=self, id="DbCodedeployApp")
        # deploy_group = codedeploy.EcsDeploymentGroup(
        #     scope=self,
        #     id="DbCodedeployGroup",
        #     blue_green_deployment_config=codedeploy.EcsBlueGreenDeploymentConfig(
        #         blue_target_group=blue_target_group,
        #         green_target_group=green_target_group,
        #         listener=listener,
        #     ),
        #     service=db_service,
        #     application=deploy_app,
        # )


class HypermediaStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        vpc = ec2.Vpc(
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
        vpc.add_interface_endpoint(
            id="EndpointSsmMessages",
            service=ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES,
            subnets=ec2.SubnetSelection(),
        )
        vpc.add_interface_endpoint(
            id="EndpointLogs",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
        )
        vpc.add_interface_endpoint(
            id="EndpointSecretsManager",
            service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
        )
        cluster = ecs.Cluster(
            scope=self,
            id="EcsCluster",
            container_insights=True,
            default_cloud_map_namespace=ecs.CloudMapNamespaceOptions(
                name="getogrand-hypermedia"
            ),
            enable_fargate_capacity_providers=True,
            execute_command_configuration=ecs.ExecuteCommandConfiguration(),
            vpc=vpc,
        )
        cluster.add_default_capacity_provider_strategy(
            [ecs.CapacityProviderStrategy(capacity_provider="FARGATE_SPOT", weight=1)]
        )
        file_system = efs.FileSystem(scope=self, id="Efs", vpc=vpc)
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
            self,
            "Secret",
            "arn:aws:secretsmanager:ap-northeast-2:730335367003:secret:getogrand-hypermedia-ImNX6Q",
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

        db_service = DbService(
            scope=self,
            id="DbService",
            cluster=cluster,
            task_exec_role=task_exec_role,
            task_role=task_role,
            file_system=file_system,
            secret=secret,
        )


app = App()
HypermediaStack(app, "GetograndHypermedia")
app.synth()
