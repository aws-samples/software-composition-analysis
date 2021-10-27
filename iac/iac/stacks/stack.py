from aws_cdk import (core)
from iac.constructs.ci import CIConstruct

class MainStack(core.Stack):

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        repo_name = core.CfnParameter(
            self,
            "CodeCommitName",
            type="String",
            default='MyRepositoryName',
            description="Name of CodeCommit repo to tie with the scanning solution"
        )

        snyk_org_id = core.CfnParameter(
            self,
            "SnykOrgId",
            type="String",
            default='SnykPSOrg',
            description="Name of SSM parameter which stores the Snyk Org ID"
        )

        snyk_auth = core.CfnParameter(
            self,
            "SnykAuthToken",
            type="String",
            default='SnykAuth',
            description="Name of SSM parameter which stores the Snyk Auth token"
        )

        props = {}
        props['codecommit-name'] = repo_name.value_as_string
        props['snyk-org-id'] = snyk_org_id.value_as_string
        props['snyk-auth-code'] = snyk_auth.value_as_string

        CIConstruct(self, 'cdk-ci-construct', props)
