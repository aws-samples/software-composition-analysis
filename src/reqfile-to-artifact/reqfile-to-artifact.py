"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
SPDX-License-Identifier: MIT-0

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import logging
import boto3
from botocore.exceptions import ClientError
import requests
import os

ca_client = boto3.client("codeartifact")
domain = os.environ.get("DOMAIN")
domain_owner = os.environ.get("DOMAIN_OWNER")
repository = os.environ.get("REPOSITORY")
project_name = os.environ.get("CODEBUILD_PROJECT_NAME")
bucket = os.environ.get("BUCKET")
lang_format = "pypi"


def get_latest_version_number(package_name: str) -> str:
    """
    Obtain the latest version of a given package name from Pypi.
    """

    r = requests.get(os.path.join("https://pypi.org/pypi/", package_name, "json"))
    return r.json().get("info").get("version")


def get_packages_list(packages: list = [], **kwargs) -> list:
    """
    Obtain list of existing packages in the CodeArtifact repository.
    """

    response = ca_client.list_packages(
        domain=domain,
        domainOwner=domain_owner,
        repository=repository,
        format=lang_format,
        **kwargs
    )
    if "nextToken" in response:
        packages = get_packages_list(packages=packages,
                                     nextToken=response["nextToken"],
                                     )
    packages.extend([p["package"] for p in response["packages"]])
    return packages


def get_package_version(new_package: str, versions: list = [], **kwargs) -> list:
    """
    Obtain list of versions per given package
    """
    try:
        response = ca_client.list_package_versions(
            domain=domain,
            domainOwner=domain_owner,
            repository=repository,
            format=lang_format,
            package=new_package,
            **kwargs
        )

        if "nextToken" in response:
            versions = get_package_version(new_package=new_package,
                                           versions=versions,
                                           nextToken=response["nextToken"],
                                           )

        versions.extend([i["version"] for i in response["versions"]])
        return versions

    except ClientError as error:
        if error.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"Package {new_package} does not exists in the repo")
            return[]


def get_package_names_and_versions(requirements_file: str) -> list:
    """
    Strip the requirements file to packages with versions and those without.
    Obtain the latest version if needed.
    """
    with_ver_reqlist = {}

    for package in requirements_file:
        split_location = package.find("==")
        if split_location > 0:
            package_name = package[:split_location].lower()
            pakcage_version = package[split_location+2:]

            with_ver_reqlist[package_name] = pakcage_version
        else:
            latest_version = get_latest_version_number(package)
            with_ver_reqlist[package] = latest_version

    return with_ver_reqlist


def trigger_cb(file_name: str, commit_hash: str, project_name: str) -> None:
    """
    Trigger a CodeBuild project to initiate the scan process.
    """

    cb_client = boto3.client("codebuild")
    build = {
        "projectName": project_name,
        "sourceVersion": commit_hash,
        "environmentVariablesOverride": [
            {"name": "REQ_FILENAME", "value": file_name, "type": "PLAINTEXT"}
        ],
    }
    cb_client.start_build(**build)


def upload_file(file_name: str, bucket: str, object_name: str =None) -> None:
    """
    Upload a file to a S3 bucket.
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name

    # Upload the file
    s3_client = boto3.client("s3")
    try:
        s3_client.upload_file(file_name, bucket, object_name)
    except ClientError as e:
        logging.error(e)


def final_missing_list(with_ver_reqlist, missing_packages_from_repo):
    new_packages = []
    for package, version in with_ver_reqlist.items():
        if package in missing_packages_from_repo:
            print(package, version, "added to missing")
            new_packages.append(f"{package}=={version}")
        elif with_ver_reqlist[package] in get_package_version(package):
            print(package, " same version already exists")
        else:
            print(f"{package}=={version}", "added (ver) to missing")
            new_packages.append(f"{package}=={version}")
    return new_packages


def lambda_handler(event, context):
    requirements_file = event["responsePayload"]["changed_packages"]
    commit_hash = event["responsePayload"]["commit_id"]
    print("input: " + str(requirements_file))
    with_ver_reqlist = get_package_names_and_versions(requirements_file)
    missing_packages_from_repo = set(with_ver_reqlist.items()) - set(get_packages_list())
    new_packages = final_missing_list(
        with_ver_reqlist, missing_packages_from_repo
    )
    if new_packages:
        file_name = f"requirements-{commit_hash}.txt"
        local_file_path = os.path.join("/tmp", file_name)
        with open(local_file_path, "w") as f:
            for item in new_packages:
                f.write(f"{item}\n")

        print("missing req", new_packages)
        upload_file(
            local_file_path, bucket, object_name=f"requirements_files/{file_name}"
        )
        trigger_cb(file_name, commit_hash, project_name)
    else:
        print("nothing has been changed")
