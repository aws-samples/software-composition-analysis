from aws_cdk import (
    core,
    aws_iam as iam,
    aws_codecommit as codecommit,
    aws_codebuild as codebuild,
    aws_codeartifact as codeartifact,
    aws_kms as kms,
    aws_lambda as _lambda,
    aws_lambda_destinations as destinations,
    aws_s3 as s3,
)
import os


class CIConstruct(core.Construct):
    def __init__(
        self, scope: core.Construct, construct_id: str, props, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        codecommit_principal = iam.ServicePrincipal("codecommit.amazonaws.com")
        self.artifacts_bucket = s3.Bucket(self, "artifacts-bucket")
        self.domain_enc_key = kms.Key(self, "codeartifact-domain-kms")

        self.codecommit_repo = codecommit.Repository(
            self,
            "python-repo",
            repository_name=f"{props.get('codecommit-name')}",
            description="Some description.",
        )
        self.codeartifact_domain = codeartifact.CfnDomain(
            self,
            "codeartifact-domain",
            domain_name="dummy-domain",
            encryption_key=self.domain_enc_key.key_arn,
        )
        self.codeartifact_repo = codeartifact.CfnRepository(
            self,
            "py-codeartifact",
            domain_name=self.codeartifact_domain.domain_name,
            repository_name="dummy-repo",
        )
        self.codeartifact_repo.add_depends_on(self.codeartifact_domain)
        
        self.snyk_build_project = codebuild.Project(
            self,
            "SnykScan",
            build_spec=codebuild.BuildSpec.from_object(
                {
                    "version": "0.2",
                    "env": {
                        "parameter-store": {
                            "SNYK_TOKEN": props["snyk-auth-code"],
                            "SNYK_ORG": props["snyk-org-id"],
                        }
                    },
                    "phases": {
                        "install": {
                            "commands": [
                                "echo 'Installing Snyk'",
                                "npm install -g snyk",
                            ]
                        },
                        "pre_build": {
                            "commands": [
                                "echo Authorizing Snyk",
                                "snyk config set api=${SNYK_TOKEN}",
                                f"aws s3 cp s3://{self.artifacts_bucket.bucket_name}/requirements_files/${{REQ_FILENAME}} .",
                            ]
                        },
                        "build": {
                            "commands": [
                                "echo Installing requiremnets",
                                "pip3 install -r ${REQ_FILENAME}",
                                "echo Executing Snyk scan",
                                "snyk test --file=${REQ_FILENAME} --org=${SNYK_ORG} --package-manager=pip > results_output",
                            ]
                        },
                        "post_build": {
                            "commands": [
                                "if [[ $CODEBUILD_BUILD_SUCCEEDING == 0 ]]; \
                                                                        then echo '@@@@@@@@ Snyk found vulnerabilities, \
                                                                        Aborting @@@@@@@'; exit 255; fi",
                                "pip3 install twine",
                                "mkdir downloaded_pakacges",
                                "pip3 download -r ${REQ_FILENAME} -d downloaded_pakacges",
                                f"aws codeartifact login --tool twine --domain {self.codeartifact_domain.domain_name} --domain-owner {core.Aws.ACCOUNT_ID} --repository {self.codeartifact_repo.repository_name}",
                                "twine upload --repository codeartifact downloaded_pakacges/*",
                            ]
                        },
                    },
                    "artifacts": {
                        "files": ["results_output"],
                        "name": "results_output-$(date +%Y-%m-%d)",
                    },
                }
            ),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_3,
                compute_type=codebuild.ComputeType.LARGE,
            ),
            artifacts=codebuild.Artifacts.s3(
                bucket=self.artifacts_bucket,
                include_build_id=True,
                path="artifacts",
                package_zip=False,
            ),
        )

        self.requests_lambda_layer = _lambda.LayerVersion.from_layer_version_arn(self, "requests-layer",
                                                                                 "arn:aws:lambda:us-east-1:770693421928:layer:Klayers-python38-requests:24")
        self.reqfile_to_artifact = _lambda.Function(
            self,
            "reqfile_to_artifact",
            runtime=_lambda.Runtime.PYTHON_3_7,
            layers=[self.requests_lambda_layer],
            handler="reqfile-to-artifact.lambda_handler",
            code=_lambda.Code.from_asset(
                os.path.join(
                    os.path.dirname("."), "..", "src", "reqfile-to-artifact"
                )
            ),
            environment={
                "DOMAIN": f"{self.codeartifact_domain.domain_name}",
                "DOMAIN_OWNER": f"{core.Aws.ACCOUNT_ID}",
                "REPOSITORY": f"{self.codeartifact_repo.repository_name}",
                "CODEBUILD_PROJECT_NAME": f"{self.snyk_build_project.project_name}",
                "BUCKET": f"{self.artifacts_bucket.bucket_name}",
            },
        )

        self.calc_changes_lambda = _lambda.Function(
            self,
            "calc_changes_lambda",
            runtime=_lambda.Runtime.PYTHON_3_7,
            handler="trigger-changed-files.lambda_handler",
            code=_lambda.Code.from_asset(
                os.path.join(
                    os.path.dirname("."), "..", "src", "trigger-changed-files"
                )
            ),
            on_success=destinations.LambdaDestination(self.reqfile_to_artifact),
        )

        self.calc_changes_lambda.grant_invoke(codecommit_principal)
        self.calc_changes_lambda.role.add_to_policy(
            iam.PolicyStatement(
                resources=[f"arn:aws:codecommit:{core.Aws.REGION}:{core.Aws.ACCOUNT_ID}:{props.get('codecommit-name')}"],
                actions=[
                    "codecommit:GetTree",
                    "codecommit:BatchGetCommits",
                    "codecommit:GetCommit",
                    "codecommit:GetCommitHistory",
                    "codecommit:GetDifferences",
                    "codecommit:GetReferences",
                    "codecommit:GetObjectIdentifier",
                    "codecommit:BatchGetCommits",
                    "codecommit:GetBlob"
                ],
            )
        )
        
        self.codeartifact_repo_packages = f"arn:aws:codeartifact:{core.Aws.REGION}:{core.Aws.ACCOUNT_ID}:package/{self.codeartifact_domain.domain_name}/{self.codeartifact_repo.repository_name}/pypi/*/*"
        self.artifacts_bucket.grant_write(self.reqfile_to_artifact)
        self.reqfile_to_artifact.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "codeartifact:ListPackages",
                    "codeartifact:ListPackageVersions",
                ],
                effect=iam.Effect.ALLOW,
                resources=[self.codeartifact_repo.attr_arn, self.codeartifact_repo_packages],
            )
        )

        self.codecommit_repo.notify(
            arn=self.calc_changes_lambda.function_arn, name="lambda-trigger"
        )

        self.snyk_build_project.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameters"],
                effect=iam.Effect.ALLOW,
                resources=[
                    f"arn:aws:ssm:{core.Aws.REGION}:{core.Aws.ACCOUNT_ID}:parameter/{props['snyk-auth-code']}",
                    f"arn:aws:ssm:{core.Aws.REGION}:{core.Aws.ACCOUNT_ID}:parameter/{props['snyk-org-id']}",
                ],
            )
        )
        self.snyk_build_project.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "codeartifact:GetRepositoryEndpoint",
                    "codeartifact:ReadFromRepository",
                    "codeartifact:PublishPackageVersion",
                ],
                effect=iam.Effect.ALLOW,
                resources=[self.codeartifact_repo.attr_arn, self.codeartifact_repo_packages],
            )
        )
        self.snyk_build_project.add_to_role_policy(iam.PolicyStatement(
             actions=['sts:GetServiceBearerToken'],
             effect=iam.Effect.ALLOW,
             resources=["*"],
             conditions={"StringEquals": {"sts:AWSServiceName": "codeartifact.amazonaws.com"}}
         ))
        self.snyk_build_project.add_to_role_policy(iam.PolicyStatement(
             actions=['codeartifact:GetAuthorizationToken'],
             effect=iam.Effect.ALLOW,
             resources=["*"]
         ))

        self.reqfile_to_artifact.add_to_role_policy(
            iam.PolicyStatement(
                actions=["codebuild:StartBuild"],
                effect=iam.Effect.ALLOW,
                resources=[self.snyk_build_project.project_arn],
            )
        )

        self.artifacts_bucket.grant_read_write(self.snyk_build_project)
