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

import os
import boto3

codecommit = boto3.client('codecommit')


def get_last_commit_log(repository, commit_id):
    response = codecommit.get_commit(
        repositoryName=repository,
        commitId=commit_id
    )
    return response['commit']


def get_file_differences(repository_name, last_commit_id, previous_commit_id):
    response = None
    extra_kwargs = {}

    if previous_commit_id != None:
        extra_kwargs["beforeCommitSpecifier"] = previous_commit_id

    response = codecommit.get_differences(
        repositoryName=repository_name,
        afterCommitSpecifier=last_commit_id,
        **extra_kwargs)

    differences = []

    if response == None:
        return differences

    while "nextToken" in response:
        response = codecommit.get_differences(
            repositoryName=repository_name,
            beforeCommitSpecifier=previous_commit_id,
            afterCommitSpecifier=last_commit_id,
            nextToken=response["nextToken"]
        )
        differences += response.get("differences", [])
    else:
        differences += response["differences"]

    return differences


def get_last_commit_id(repository, branch="main"):
    response = codecommit.get_branch(
        repositoryName=repository,
        branch_name=branch
    )
    return response['branch']['commitId']


def lambda_handler(event, context):
    # Initialize needed variables
    file_extension_allowed = [".txt"]
    file_names_allowed = ["requirements"]
    commit_hash = event['Records'][0]['codecommit']['references'][0]['commit']

    repo_name = event['Records'][0]['eventSourceARN'].split(':')[-1]
    branch_name = os.path.basename(
        str(event['Records'][0]['codecommit']['references'][0]['ref']))

    # Get commit ID for fetching the commit log
    if (commit_hash == None) or (commit_hash == '0000000000000000000000000000000000000000'):
        commit_hash = get_last_commit_id(repo_name, branch_name)

    last_commit = get_last_commit_log(repo_name, commit_hash)

    previous_commit_id = None
    if len(last_commit['parents']) > 0:
        previous_commit_id = last_commit['parents'][0]

    differences = get_file_differences(repo_name, commit_hash, previous_commit_id)
    for diff in differences:
        root, extension = os.path.splitext(str(diff['afterBlob']['path']))
        file_name = os.path.basename(str(diff['afterBlob']['path']))
        if ((extension in file_extension_allowed) or (file_name in file_names_allowed)):
            # Extract the actual changes
            after_blob = diff['afterBlob']['blobId']
            after_changes = set(codecommit.get_blob(repositoryName=repo_name, blobId=after_blob)['content'].decode().split())

            before_blob = diff['beforeBlob']['blobId']
            before_changes = set(codecommit.get_blob(repositoryName=repo_name, blobId=before_blob)['content'].decode().split())

            added_modified_packages = list(after_changes - before_changes)

    return {
        'changed_packages': added_modified_packages,
        'commit_id': commit_hash
        }