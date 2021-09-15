# 通过EnginFrame, AWS ParallelCluster, 和Amazon Aurora实现HPC高可用架构 

本方案代码**适用于AWS中国区域部署**，提出的解决方案旨在简化在AWS云的按需集群上设置和运行高性能计算应用的过程；实现了跨可用区的高性能计算的高可用。它的部署使用了AWS云开发者工具包（AWS CDK），这是一个软件开发框架，用于在代码中定义云基础设施，并通过AWS CloudFormation进行配置，隐藏了组件之间集成的复杂性。

值的注意的地方**enginframe目前只支持x86架构实例**，ARM架构暂未支持，所以整套方案都是部署在x86架构的实例上。

该方案基于[这篇博客](https://aws.amazon.com/blogs/hpc/highly-available-hpc-infrastructure-on-aws)，并参考适用用于[AWS Global区域的代码](https://github.com/aws-samples/enginframe-aurora-serverless)

以下包括该解决方案的主要组成部分。

- Amazon Aurora是一个完全管理的关系型数据库引擎，与MySQL和PostgreSQL兼容。Aurora可以提供高达5倍于MySQL的吞吐量和高达3倍于PostgreSQL的吞吐量，而不需要对您的大多数现有应用程序进行修改。在这个解决方案中，Aurora被用作EnginFrame的后端数据库，采用无服务器配置。
- AWS ParallelCluster是一个由AWS支持的开源集群管理工具，使你能够轻松地在AWS上部署和管理HPC集群。AWS ParallelCluster使用一个简单的文本文件来建模，并以自动化和安全的方式为您的HPC应用提供所有需要的资源。它还支持各种作业调度器，如AWS Batch、SGE、Torque和Slurm，以方便作业提交。
- EnginFrame是一个领先的支持网格的应用门户，用于用户友好地提交、控制和监控HPC作业和互动远程会话。它包括对HPC作业生命周期所有阶段的复杂数据管理，并与大多数流行的作业调度器和中间件工具集成，以提交、监控和管理作业。EnginFrame提供了一个模块化的系统，可以很容易地添加新的功能（如应用集成、认证源、许可证监控等）。它还具有复杂的网络服务接口，除了为你自己的环境开发定制解决方案外，还可以利用它来增强现有的应用程序。
- 亚马逊弹性文件系统（Amazon EFS）提供了一个简单的、无服务器的、可设置可遗忘的弹性文件系统，让你无需配置或管理存储就可以共享文件数据。它可以与AWS云服务和企业内部资源一起使用，并且可以按需扩展到PB级而不影响应用。有了亚马逊EFS，您可以在添加和删除文件时自动增长和缩小您的文件系统，而不需要为适应增长而配置和管理容量。
- Amazon FSx for Lustre是一项完全可管理的服务，为计算工作负载提供成本效益高、高性能、可扩展的存储。许多工作负载，如HPC，依赖于计算实例通过高性能共享存储访问同一组数据。
这两个集群是使用AWS ParallelCluster创建的，用于访问环境的主要前端是由EnginFrame在企业配置中管理的。Amazon Aurora被EnginFrame用作RDBMS来管理Triggers、Job-Cache以及Applications和View用户组。Amazon Elastic File System被用作两个集群环境之间的共享文件系统。两个Amazon FSx文件系统，每个可用区（AZ）一个，被用作高性能文件系统，用于HPC作业。

该配置涵盖了两个不同的可用区，以便在一个特定的AZ发生故障时保持一个完全可操作的系统。此外，如果两个可用区中的一个没有特定的实例类型，你可以为你的工作使用两个可用区。

下图显示了HPC解决方案的不同组件。该架构显示了用户如何与EnginFrame互动，在AWS ParallelCluster创建的两个集群中启动HPC作业。  

![方案架构图](/ha-hpc-arch.png "方案架构图")

### Creation of the default account password:

EnginFrame默认的管理员账户名为efadmin，需要一个密码。为了提高解决方案的安全性，该密码必须由用户创建并保存在AWS Secrets Manager中。[AWS Secrets Manager教程](https://docs.aws.amazon.com/secretsmanager/latest/userguide/tutorials_basic.html)解释了如何创建秘密。密码必须有字母、数字和一个特殊字符。创建的秘密的ARN将在后面使用。
这个示例命令可以用来从AWS cli中创建密码。 
```
$ aws secretsmanager create-secret --name efadminPassword --description "EfadminPassword" --secret-string '{"efadminPassword":"test123456!"}' 
```

### 以下对关键代码和设置进行说明:

- [app.py](/app.py)包含用于部署环境的配置变量。在部署之前，你必须用所需的配置对其进行定制。
```
import os

from aws_cdk import core as cdk

from aws_cdk import core

from enginframe_aurora_serverless.vpc import VpcStack
from enginframe_aurora_serverless.aurora_serverless import AuroraServerlessStack
from enginframe_aurora_serverless.efs import EfsStack
from enginframe_aurora_serverless.alb import AlbStack
from enginframe_aurora_serverless.enginframe import EnginFrameStack
from enginframe_aurora_serverless.fsx import FsxStack


CONFIG = {
    "ec2_type_enginframe": "t2.2xlarge",  # EnginFrame实例类型
    # ARN of the secret that contains the efadmin password
    "arn_efadmin_password": "<arn_secret>",
    "key_name": "<key_name>",  # SSH key name that you already have in your account
    "ebs_engingframe_size": 50,  # EBS size for EnginFrame,
    "fsx_size": 1200,  # fsx scratch 的大小
    "jdbc_driver_link": "<jdbc_driver_link>", # 你可以在这个链接下载: https://dev.mysql.com/downloads/connector/j/ . 你需要选择TAR Archive Platform indipended版本.
    "pcluster_version": "2.10.3"  # Parallel Cluster安装的版本
}


env = core.Environment(
    account=os.environ.get("CDK_DEPLOY_ACCOUNT",
                           os.environ["CDK_DEFAULT_ACCOUNT"]),
    region=os.environ.get("CDK_DEPLOY_REGION",
                          os.environ["CDK_DEFAULT_REGION"])
)

app = core.App()
vpc_stack = VpcStack(app, "VPC", env=env)
aurora_stack = AuroraServerlessStack(
    app, "AuroraServerless", vpc=vpc_stack.vpc, env=env)
efs_stack = EfsStack(app, "EFS", vpc=vpc_stack.vpc, env=env)
fsx_stack = FsxStack(app, "FSX", vpc=vpc_stack.vpc, config=CONFIG, env=env)
alb_stack = AlbStack(app, "ALB", vpc=vpc_stack.vpc, env=env)
enginframe_stack = EnginFrameStack(app, "EnginFrame", vpc=vpc_stack.vpc, efs=efs_stack.file_system, aurora=aurora_stack.db,
                                   alb_security_group=alb_stack.alb_security_group,
                                   certificate=alb_stack.certificate, config=CONFIG, lb_enginframe=alb_stack.lb_enginframe, fsx1=fsx_stack.file_system_1, fsx2=fsx_stack.file_system_2, env=env)

app.synth()
```
<key_name>是你的亚马逊EC2密钥对。<arn_secret>是在上一步中创建的秘密的ARN。
- 以下的额外参数也可以根据你的要求进行相应的配置。
  - ec2_type_enginframe。EnginFrame实例类型。
  - ebs_engingframe_size。EnginFrame实例的亚马逊弹性块存储（EBS）大小。
  - fsx_size：Lustre卷的FSx的大小。
  - jdbc_driver_link：用于下载MySQL JDBC驱动程序的链接。MySQL社区下载包含最新版本。需要的版本是独立于TAR存档平台的版本。
  - pcluster_version：环境中安装的AWS ParallelCluster版本。该解决方案已经用2.10.3版本进行了测试。
- enginframe_aurora_serverless目录包含用于部署所需资源的类文件。其中[aurora_serverless.py](/enginframe_aurora_serverless/aurora_serverless.py)改动较大，原方案采用Aurora Serverless，由于AWS中国北京区还未发布，所以如果在北京区域部署改成兼容MySQL的Aurora实例数据库集群，如下CDK代码：  
```
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
```
如果部署在宁夏区域，可以采用Aurora Serverless, CDK代码如下
```
        self.db = rds.ServerlessCluster(
            self,
            id="AuroraServerlessDB",
            vpc=vpc,
            engine=rds.DatabaseClusterEngine.AURORA_MYSQL,
            cluster_identifier=db_cluster_name,
            default_database_name="enginframedb",
            security_groups=[security_group],
            subnet_group=subnet_group,
            removal_policy=core.RemovalPolicy.DESTROY
        )
```
- lambda/cert.py是用于创建应用负载平衡器证书的Lambda函数。
- lambda_destroy_pcluster/destroy.py是用于在删除堆栈时销毁AWS ParallelCluster集群的Lambda函数。
- 用户数据目录包含用于配置HPC环境的脚本。
- scripts/pcluster.config是AWS ParallelCluster的配置文件。
- scripts/post_install.sh是AWS ParallelCluster的后期安装脚本。

### 进行方案部署：

```
$ python3 -m venv .venv
$ source .venv/bin/activate
$ python3 -m pip install -r requirements.txt
$ cdk bootstrap aws://<account>/<region>
$ cdk deploy VPC AuroraServerless EFS FSX ALB EnginFrame
```
该部署使用默认配置，创建了以下组件。

- 两个EnginFrame实例，每个AZ一个
- 两个群集头节点实例，每个AZ一个
- 一个Amazon EFS文件系统
- 两个FSx for Lustre文件系统，每个AZ一个
- 一个Aurora MySQL数据库集群
- 一个应用负载平衡器ALB
### 文件系统结构
该解决方案包含以下共享文件系统。

- /efs是两个集群之间共享的文件系统，可以用来安装你的应用程序。
- /fsx_cluster1和/fsx_cluster2是相关集群的高性能文件系统，可用于包含你的抓取和输入输出文件。
部署完成后，注意应用负载平衡器的URL地址。下面是一个输出的例子。

```
Outputs:
EnginFrame.EnginFramePortalURL = https://ALB-EFLB1F2-TJNAWWLF3LFT-1892922852.cn-north-1.elb.amazonaws.com.cn
```
这个地址将被用来访问EnginFrame门户。  

![EnginFrame门户](/ha-hpc-efportal.png "EnginFrame门户")
