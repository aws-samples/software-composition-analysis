# How to automate your software-composition analysis on AWS

The following steps automate a vulnerability scan of a new public package:

1. Capture events when adding new packages into the requirements file of the application.
2. Process the changes, and verify that the package does not exist in the current AWS CodeCommit repository.
3. Triggering AWS CodeBuild build to download the package, scan it, and upload to the internal repository.
4. If the package or package dependencies contains any vulnerability, the build will fail and a detailed report will be generated.
## ![](/Images/software-composition-analysis-architecture-diagram.jpg)

Detailed instructions here:  https://aws.amazon.com/blogs/infrastructure-and-automation/how-to-automate-your-software-composition-analysis-on-aws/

1. A developer adds a new package or updates a version of an existing package into the relevant requirements file (for example, in Python, it is requirements.txt)
2. After the change is committed and pushed to AWS CodeCommit repository, a trigger invokes a Lambda function. The function contains Python code that extracts only the changes, to avoid the overhead of working on the entire dependency list.
3. The AWS Lambda then triggers another Lambda function that compares the changes to your existing internal repository.
    * If the exact package version already exists, there are no further actions.
4. Otherwise, an AWS CodeBuild project is invoked by Lambda.
5. AWS CodeBuild project takes the added or changed packages, downloads them from the public repository (in this case, Python uses pypi.org) into a sandbox container.
6. A Snyk tool is used to scan the packages for known vulnerabilities.
    * If the scan is successful, it is uploaded to AWS CodeArtifact and ready ready for use.
    * If the scan fails, a detailed report is generated for further investigation.

## Prerequisites
* An AWS account (use a Region that supports AWS CodeCommit, AWS CodeBuild, and AWS CodePipeline. For more information, see [AWS Regional Services](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/)).
* A basic understanding of the following AWS Services:
    * AWS CodeBuild
    * AWS CodeCommit
    * AWS CodeArtifact
    * AWS Lambda
    * AWS Systems Manager Parameter Store
* A [Snyk account](https://snyk.co/AWS-CodePipeline-blog) (note that Snyk is third-party * software).
* A basic understanding of Python.
* A basic understanding of Git.
* A basic understanding of [CDK environments](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/).

## How to deploy this Template

Clone the CDK code from the GitHub repository:
```
git clone https://github.com/aws-samples/software-composition-analysis
```

Navigate to the `iac` directory of the cloned repository, and run the following command:
```
cdk deploy
--parameters CodeCommitName=<name-of-codecommit-repo> \
--parameters SnykOrgId=<value> \
--parameters SnykAuthToken=<value>
```
The previous command adds a new AWS CloudFormation template, which creates an AWS CodeCommit git repository to hold the source code, a CodeBuild build server, a CodeArtifact repository to hold the scanned packages, and two Lambda functions.

For additional information check the [blogpost page](https://aws.amazon.com/blogs/infrastructure-and-automation/how-to-automate-your-software-composition-analysis-on-aws/)


##  Cleanup

To avoid accruing further cost for the resources deployed in this solution, run cdk destroy to remove all the AWS resources deployed through CDK. The output of a successful deletion should look like the following:

Run

```
cdk destroy
```


## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
