## Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
## SPDX-License-Identifier: MIT-0
#!/usr/bin/env python3

from aws_cdk import core
from iac.stacks.stack import MainStack

app = core.App()
MainStack(app, "cdk-stack")

app.synth()
