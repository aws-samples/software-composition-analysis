## Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
## SPDX-License-Identifier: MIT-0
import setuptools


with open("README.md") as fp:
    long_description = fp.read()


setuptools.setup(
    name="iac",
    version="0.0.1",

    description="An empty CDK Python app",
    long_description=long_description,
    long_description_content_type="text/markdown",

    author="author",

    package_dir={"": "iac"},
    packages=setuptools.find_packages(where="iac"),

    install_requires=[
        "aws-cdk.core==1.116.0",
        "aws-cdk.aws_iam==1.116.0",
        "aws-cdk.aws_codecommit==1.116.0",
        "aws-cdk.aws_codebuild==1.116.0",
        "aws_cdk.aws_codeartifact==1.116.0",
        "aws_cdk.aws_lambda_destinations==1.116.0",
    ],

    python_requires=">=3.6",

    classifiers=[
        "Development Status :: 4 - Beta",

        "Intended Audience :: Developers",

        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",

        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",

        "Typing :: Typed",
    ],
)
