from aws_cdk import (
    App,
    Stack,
    Environment,
    Duration,
    aws_ecs as ecs,
    aws_ecs_patterns as patterns,
    aws_ec2 as ec2,
    aws_efs as efs,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_ecr as ecr,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_elasticloadbalancingv2 as elbv2,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as cforigins,
    aws_codepipeline as pipeline,
    aws_codepipeline_actions as pipeline_actions,
    aws_codebuild as codebuild,
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
    ):
        super().__init__(scope, id)
        self.task_volumes = [
            ecs.Volume(
                name="db-volume",
                efs_volume_configuration=ecs.EfsVolumeConfiguration(
                    file_system_id=file_system.file_system_id
                ),
            )
        ]
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
            volumes=self.task_volumes,
        )
        self.image_repo = ecr.Repository.from_repository_arn(
            scope=self,
            id="ImageRepo",
            repository_arn="arn:aws:ecr:ap-northeast-2:730335367003:repository/getogrand-hypermedia/db",
        )
        self.container = self.task_def.add_container(
            id="Container",
            image=ecs.ContainerImage.from_ecr_repository(self.image_repo),
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "pg_isready -U postgres"]
            ),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="hypermedia-db"),
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
            task_definition=self.task_def,
            assign_public_ip=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            cloud_map_options=ecs.CloudMapOptions(name="db"),
            cluster=cluster,
            desired_count=1,
            enable_execute_command=True,
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(capacity_provider="FARGATE_SPOT", weight=1)
            ],
        )
        self.service.node.add_dependency(
            cluster
        )  # 서비스 삭제가 클러스터 삭제 전에 이루어지도록 설정
        self.service.connections.allow_from_any_ipv4(
            ec2.Port(
                protocol=ec2.Protocol.TCP,
                string_representation=f"{5432}",
                from_port=5432,
                to_port=5432,
            )
        )
        file_system.connections.allow_from(self.service.connections, ec2.Port.NFS)


class AppService(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        public_hosted_zone: route53.IPublicHostedZone,
        cluster: ecs.ICluster,
        task_exec_role: iam.IRole,
        task_role: iam.IRole,
        secret: secretsmanager.ISecret,
    ):
        super().__init__(scope, id)
        self.task_def = ecs.FargateTaskDefinition(
            scope=self,
            id="TaskDef",
            cpu=512,
            memory_limit_mib=1024,
            execution_role=task_exec_role,
            task_role=task_role,
        )
        self.img_repo = ecr.Repository.from_repository_arn(
            scope=self,
            id="ImageRepo",
            repository_arn="arn:aws:ecr:ap-northeast-2:730335367003:repository/getogrand-hypermedia/app",
        )
        self.container = self.task_def.add_container(
            id="Container",
            image=ecs.ContainerImage.from_ecr_repository(self.img_repo),
            health_check=ecs.HealthCheck(
                command=[
                    "CMD-SHELL",
                    "wget --quiet --spider http://localhost:8000/health",
                ]
            ),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="hypermedia-app"),
            port_mappings=[ecs.PortMapping(container_port=8000, host_port=8000)],
            secrets={
                "SECRET_KEY": ecs.Secret.from_secrets_manager(
                    secret=secret, field="django-secret-key"
                ),
                "DB_PASSWORD": ecs.Secret.from_secrets_manager(
                    secret=secret, field="db-password"
                ),
            },
            environment={"DEBUG": "False", "DB_HOST": "db.map.getogrand.media"},
            working_directory="/app",
            command=[
                "sh",
                "-c",
                "python manage.py migrate && gunicorn",
            ],
        )
        self.service = patterns.ApplicationLoadBalancedFargateService(
            scope=self,
            id="Service",
            assign_public_ip=True,
            health_check=ecs.HealthCheck(
                command=[
                    "CMD-SHELL",
                    "wget --quiet --spider http://localhost:8000/health",
                ]
            ),
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(capacity_provider="FARGATE_SPOT", weight=1)
            ],
            certificate=acm.Certificate.from_certificate_arn(
                scope=self,
                id="Certificate",
                certificate_arn="arn:aws:acm:ap-northeast-2:730335367003:certificate/12a5b4a1-a168-4604-99be-32c37f29f62b",
            ),
            cloud_map_options=ecs.CloudMapOptions(name="app"),
            circuit_breaker=ecs.DeploymentCircuitBreaker(enable=True, rollback=True),
            cluster=cluster,
            desired_count=1,
            domain_name="app.getogrand.media",
            domain_zone=public_hosted_zone,
            enable_ecs_managed_tags=True,
            enable_execute_command=True,
            health_check_grace_period=Duration.seconds(5),
            idle_timeout=Duration.seconds(30),
            protocol=elbv2.ApplicationProtocol.HTTPS,
            redirect_http=True,
            target_protocol=elbv2.ApplicationProtocol.HTTP,
            task_definition=self.task_def,
        )
        self.service.target_group.configure_health_check(enabled=True, path="/health")
        # 서비스 삭제가 클러스터 삭제 전에 이루어지도록 설정
        self.service.node.add_dependency(cluster)

        ecr_change_output = pipeline.Artifact()
        build_output = pipeline.Artifact()
        self.build_pipeline = pipeline.Pipeline(
            scope=self,
            id="Pipeline",
            pipeline_type=pipeline.PipelineType.V2,
            cross_account_keys=False,
            stages=[
                pipeline.StageProps(
                    stage_name="Source",
                    actions=[
                        pipeline_actions.EcrSourceAction(
                            action_name="EcrChangeDetected",
                            output=ecr_change_output,
                            repository=self.img_repo,
                        )
                    ],
                ),
                pipeline.StageOptions(
                    stage_name="Build",
                    actions=[
                        pipeline_actions.CodeBuildAction(
                            action_name="Build",
                            input=ecr_change_output,
                            outputs=[build_output],
                            project=codebuild.Project(
                                scope=self,
                                id="CodeBuildProject",
                                build_spec=codebuild.BuildSpec.from_object(
                                    {
                                        "version": "0.2",
                                        "phases": {
                                            "build": {
                                                "commands": [
                                                    r"""printf '[{"name":"Container","imageUri":"730335367003.dkr.ecr.ap-northeast-2.amazonaws.com/getogrand-hypermedia/app"}]' >imagedefinitions.json"""
                                                ]
                                            }
                                        },
                                        "artifacts": {
                                            "files": ["imagedefinitions.json"]
                                        },
                                    }
                                ),
                            ),  # type: ignore
                        )
                    ],
                ),
                pipeline.StageOptions(
                    stage_name="Deploy",
                    actions=[
                        pipeline_actions.EcsDeployAction(
                            action_name="Deploy",
                            service=self.service.service,
                            deployment_timeout=Duration.minutes(5),
                            input=build_output,
                        ),
                    ],
                ),
            ],
        )


class HypermediaStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.public_hosted_zone = (
            route53.PublicHostedZone.from_public_hosted_zone_attributes(
                scope=self,
                id="PublicHostedZone",
                hosted_zone_id="Z04398023FK9IFQP6B2HQ",
                zone_name="getogrand.media",
            )
        )
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
                )
            ],
        )
        self.cluster = ecs.Cluster(
            scope=self,
            id="EcsCluster",
            enable_fargate_capacity_providers=True,
            default_cloud_map_namespace=ecs.CloudMapNamespaceOptions(
                name="map.getogrand.media"
            ),
            execute_command_configuration=ecs.ExecuteCommandConfiguration(),
            vpc=self.vpc,
        )
        self.cluster.add_default_capacity_provider_strategy(
            [ecs.CapacityProviderStrategy(capacity_provider="FARGATE_SPOT", weight=1)]
        )
        self.file_system = efs.FileSystem(scope=self, id="Efs", vpc=self.vpc)
        self.task_role_policy = iam.Policy(
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
        self.task_role = iam.Role(
            scope=self,
            id="EcsTaskRole",
            assumed_by=iam.ServicePrincipal(service="ecs-tasks.amazonaws.com"),  # type: ignore
        )
        self.task_role_policy.attach_to_role(self.task_role)  # type: ignore
        self.secret = secretsmanager.Secret.from_secret_complete_arn(
            scope=self,
            id="Secret",
            secret_complete_arn="arn:aws:secretsmanager:ap-northeast-2:730335367003:secret:getogrand-hypermedia-ImNX6Q",
        )
        self.task_exec_role_policy = iam.Policy(
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
                        resources=[self.secret.secret_arn],
                    ),
                ]
            ),
        )
        self.task_exec_role = iam.Role(
            scope=self,
            id="EcsTaskExecRole",
            assumed_by=iam.ServicePrincipal(service="ecs-tasks.amazonaws.com"),  # type: ignore
        )
        self.task_exec_role_policy.attach_to_role(self.task_exec_role)  # type: ignore

        self.db_service = DbService(
            scope=self,
            id="DbService",
            cluster=self.cluster,
            task_exec_role=self.task_exec_role,
            task_role=self.task_role,
            file_system=self.file_system,
            secret=self.secret,
        )
        self.app_service = AppService(
            scope=self,
            id="AppService",
            cluster=self.cluster,
            public_hosted_zone=self.public_hosted_zone,
            task_exec_role=self.task_exec_role,  # type: ignore
            task_role=self.task_role,  # type: ignore
            secret=self.secret,
        )
        self.app_service.node.add_dependency(self.db_service)

        self.cf_dist = cloudfront.Distribution(
            scope=self,
            id="CloudfrontDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=cforigins.HttpOrigin(
                    domain_name="app.getogrand.media",
                    protocol_policy=cloudfront.OriginProtocolPolicy.MATCH_VIEWER,
                ),  # type: ignore
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD,
                cache_policy=cloudfront.CachePolicy(
                    scope=self,
                    id="CachePolicy",
                    cookie_behavior=cloudfront.CacheCookieBehavior.all(),
                    default_ttl=Duration.seconds(0),
                    enable_accept_encoding_brotli=True,
                    enable_accept_encoding_gzip=True,
                    header_behavior=cloudfront.CacheHeaderBehavior.allow_list(
                        "x-method-override",
                        "Origin",
                        "HX-Trigger",
                        "HX-Request",
                        "Host",
                        "HX-Prompt",
                        "HX-Target",
                        "HX-Boosted",
                    ),
                    query_string_behavior=cloudfront.CacheQueryStringBehavior.all(),
                ),
                compress=True,
                origin_request_policy=None,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            certificate=acm.Certificate.from_certificate_arn(
                scope=self,
                id="CloudfrontCertificate",
                certificate_arn="arn:aws:acm:us-east-1:730335367003:certificate/6a86ec89-eff9-4682-81c4-9e14972ef7f5",
            ),
            domain_names=["getogrand.media"],
            http_version=cloudfront.HttpVersion.HTTP2_AND_3,
            enable_ipv6=True,
            enable_logging=True,
            log_includes_cookies=True,
        )
        self.cf_alias_target = route53.RecordTarget.from_alias(
            targets.CloudFrontTarget(self.cf_dist)  # type: ignore
        )
        self.cf_a_record = route53.ARecord(
            scope=self,
            id="CloudfrontARecord",
            target=self.cf_alias_target,
            zone=self.public_hosted_zone,
        )
        self.cf_aaaa_record = route53.AaaaRecord(
            scope=self,
            id="CloudfrontAaaaRecord",
            target=self.cf_alias_target,
            zone=self.public_hosted_zone,
        )


app = App()
HypermediaStack(
    app,
    "GetograndHypermedia",
    env=Environment(account="730335367003", region="ap-northeast-2"),
)
app.synth()
