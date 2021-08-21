# MIT No Attribution
# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from aws_cdk import core as cdk

from aws_cdk import core

from aws_cdk import (
    aws_ec2 as ec2,
    aws_rds as rds,
    core,
    aws_secretsmanager as sm
)
import json

class AuroraServerlessStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, vpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        subnet_group = rds.SubnetGroup(
            self,
            id="AuroraServerlessSubnetGroup",
            description='Aurora Serverless Subnet Group',
            subnet_group_name='auroraserverlesssubnetgroup',
            vpc=vpc)


        security_group = ec2.SecurityGroup(
            self,
            id="SecurityGroup",
            vpc=vpc,
            description="Aurora SG",
            allow_all_outbound=True
        )

        security_group.add_ingress_rule(ec2.Peer.ipv4(
            vpc.vpc_cidr_block), ec2.Port.tcp(3306), "allow mysql")

        # create new secret in SecretsManager
        db_master_username = {
            "db-master-username": "admin"
        }
        secret = sm.Secret(self,
                            "db-user-password-secret",
                            description="db master user password",
                            secret_name="db-master-user-password",
                            generate_secret_string=sm.SecretStringGenerator(
                                secret_string_template=json.dumps(db_master_username),
                                generate_string_key="db-master-user-password")
        )
        db_cluster_name = "aurora-serverless-db"
        self.db = rds.DatabaseCluster(
            self,
            id="AuroraServerlessDB",
            credentials=rds.Credentials.from_generated_secret("admin"),
            engine=rds.DatabaseClusterEngine.aurora_mysql(version=rds.AuroraMysqlEngineVersion.VER_2_09_0),
            cluster_identifier=db_cluster_name,
            default_database_name="enginframedb",
            
            subnet_group=subnet_group,
            removal_policy=core.RemovalPolicy.DESTROY,
            instance_props={
                # optional , defaults to t3.medium
                "instance_type": ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.SMALL),
                "security_groups": [security_group],
                "vpc_subnets": {
                   "subnet_type": ec2.SubnetType.PRIVATE
                },
                "vpc": vpc
            }    
        )

        self.db.node.add_dependency(subnet_group)
        self.db.node.add_dependency(security_group)

        core.CfnOutput(
            self,
            id="StackName",
            value=self.stack_name,
            description="Stack Name",
            export_name=f"{self.region}:{self.account}:{self.stack_name}:stack-name"
        )

        core.CfnOutput(
            self,
            id="DatabaseName",
            value="enginframedb",
            description="Database Name",
            export_name=f"{self.region}:{self.account}:{self.stack_name}:database-name"
        )

        
        core.CfnOutput(
            self,
            id="DatabaseSecretArn",
            value=self.db.secret.secret_arn,
            description="Database Secret Arn",
            export_name=f"{self.region}:{self.account}:{self.stack_name}:database-secret-arn"
        )

        core.CfnOutput(
            self,
            id="DatabaseClusterID",
            value=self.db.cluster_identifier,
            description="Database Cluster Id",
            export_name=f"{self.region}:{self.account}:{self.stack_name}:database-cluster-id"
        )

        core.CfnOutput(
            self,
            id="AuroraEndpointAddress",
            value=self.db.cluster_endpoint.hostname,
            description="Aurora Endpoint Address",
            export_name=f"{self.region}:{self.account}:{self.stack_name}:aurora-endpoint-address"
        )

        core.CfnOutput(
            self,
            id="DatabaseMasterUserName",
            value="admin",
            description="Database Master User Name",
            export_name=f"{self.region}:{self.account}:{self.stack_name}:database-master-username"
        )
