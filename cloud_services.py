cloud_service_aliases: dict[str, str] = {

    # =========================================================================
    # AWS - Compute
    # =========================================================================
    "EC2": "EC2",
    "Amazon EC2": "EC2",

    "Lambda": "Lambda",
    "AWS Lambda": "Lambda",

    "ECS": "ECS",
    "Amazon ECS": "ECS",
    "Elastic Container Service": "ECS",

    "EKS": "EKS",
    "Amazon EKS": "EKS",
    "Elastic Kubernetes Service": "EKS",

    "Fargate": "Fargate",
    "AWS Fargate": "Fargate",

    "Batch": "Batch",
    "AWS Batch": "Batch",

    "Elastic Beanstalk": "Elastic Beanstalk",
    "Beanstalk": "Elastic Beanstalk",

    "Lightsail": "Lightsail",
    "Amazon Lightsail": "Lightsail",

    "App Runner": "App Runner",
    "AppRunner": "App Runner",
    "AWS App Runner": "App Runner",

    # =========================================================================
    # AWS - Networking
    # =========================================================================

    "VPC": "VPC",
    "Amazon VPC": "VPC",
    "Virtual Private Cloud": "VPC",

    "Route53": "Route 53",
    "Route 53": "Route 53",
    "Amazon Route 53": "Route 53",

    "CloudFront": "CloudFront",
    "Amazon CloudFront": "CloudFront",

    "API Gateway": "API Gateway",
    "APIGateway": "API Gateway",
    "Amazon API Gateway": "API Gateway",

    "Direct Connect": "Direct Connect",
    "DirectConnect": "Direct Connect",

    "Transit Gateway": "Transit Gateway",
    "TGW": "Transit Gateway",

    "Global Accelerator": "Global Accelerator",

    "ELB": "Elastic Load Balancing",
    "Elastic Load Balancer": "Elastic Load Balancing",
    "Elastic Load Balancing": "Elastic Load Balancing",
    "ALB": "Elastic Load Balancing",
    "NLB": "Elastic Load Balancing",
    "CLB": "Elastic Load Balancing",

    # =========================================================================
    # AWS - Storage
    # =========================================================================

    "S3": "S3",
    "Amazon S3": "S3",
    "Simple Storage Service": "S3",

    "EBS": "EBS",
    "Amazon EBS": "EBS",
    "Elastic Block Store": "EBS",

    "EFS": "EFS",
    "Amazon EFS": "EFS",
    "Elastic File System": "EFS",

    "FSx": "FSx",
    "Amazon FSx": "FSx",

    "Storage Gateway": "Storage Gateway",
    "AWS Storage Gateway": "Storage Gateway",

    "AWS Backup": "Backup",
    "Backup": "Backup",

    # =========================================================================
    # AWS - Databases
    # =========================================================================

    "RDS": "RDS",
    "Amazon RDS": "RDS",
    "Relational Database Service": "RDS",

    "Aurora": "Aurora",
    "Amazon Aurora": "Aurora",

    "Dynamo": "DynamoDB",
    "DynamoDB": "DynamoDB",
    "Amazon DynamoDB": "DynamoDB",

    "DocumentDB": "DocumentDB",
    "Amazon DocumentDB": "DocumentDB",

    "Neptune": "Neptune",
    "Amazon Neptune": "Neptune",

    "Redshift": "Redshift",
    "Amazon Redshift": "Redshift",

    "ElastiCache": "ElastiCache",
    "Elasticache": "ElastiCache",
    "Amazon ElastiCache": "ElastiCache",

    "Keyspaces": "Keyspaces",
    "Amazon Keyspaces": "Keyspaces",

    "Timestream": "Timestream",
    "Amazon Timestream": "Timestream",

    # =========================================================================
    # AWS - Integration
    # =========================================================================

    "SQS": "SQS",
    "Amazon SQS": "SQS",
    "Simple Queue Service": "SQS",

    "SNS": "SNS",
    "Amazon SNS": "SNS",
    "Simple Notification Service": "SNS",

    "EventBridge": "EventBridge",
    "Amazon EventBridge": "EventBridge",
    "CloudWatch Events": "EventBridge",

    "MQ": "MQ",
    "Amazon MQ": "MQ",

    "Step Functions": "Step Functions",
    "StepFunctions": "Step Functions",

    "AppSync": "AppSync",
    "AWS AppSync": "AppSync",

    # =========================================================================
    # AWS - Security
    # =========================================================================

    "IAM": "IAM",
    "AWS IAM": "IAM",
    "Identity and Access Management": "IAM",

    "Secrets Manager": "Secrets Manager",

    "KMS": "KMS",
    "Key Management Service": "KMS",

    "ACM": "Certificate Manager",
    "Certificate Manager": "Certificate Manager",
    "AWS Certificate Manager": "Certificate Manager",

    "Cognito": "Cognito",
    "Amazon Cognito": "Cognito",

    "WAF": "WAF",
    "AWS WAF": "WAF",

    "Shield": "Shield",
    "AWS Shield": "Shield",

    "GuardDuty": "GuardDuty",

    "Inspector": "Inspector",

    "Security Hub": "Security Hub",

    "Macie": "Macie",

    # =========================================================================
    # AWS - Monitoring
    # =========================================================================

    "CloudWatch": "CloudWatch",
    "Cloud Watch": "CloudWatch",
    "Amazon CloudWatch": "CloudWatch",

    "CloudTrail": "CloudTrail",
    "Amazon CloudTrail": "CloudTrail",

    "Config": "Config",
    "AWS Config": "Config",

    "SSM": "Systems Manager",
    "Systems Manager": "Systems Manager",

    "Trusted Advisor": "Trusted Advisor",

    # =========================================================================
    # AWS - DevOps
    # =========================================================================

    "CodeCommit": "CodeCommit",
    "CodeBuild": "CodeBuild",
    "CodeDeploy": "CodeDeploy",
    "CodePipeline": "CodePipeline",

    "CloudFormation": "CloudFormation",
    "CFN": "CloudFormation",

    "CDK": "CDK",
    "AWS CDK": "CDK",

    # =========================================================================
    # AWS - Analytics
    # =========================================================================

    "Athena": "Athena",
    "Glue": "Glue",
    "EMR": "EMR",
    "Elastic MapReduce": "EMR",
    "Kinesis": "Kinesis",
    "OpenSearch": "OpenSearch",
    "OpenSearch Service": "OpenSearch",
    "Elasticsearch Service": "OpenSearch",
    "Amazon Elasticsearch Service": "OpenSearch",
    "QuickSight": "QuickSight",

    # =========================================================================
    # AWS - AI
    # =========================================================================

    "SageMaker": "SageMaker",
    "Amazon SageMaker": "SageMaker",

    "Bedrock": "Bedrock",
    "Amazon Bedrock": "Bedrock",

    "Textract": "Textract",
    "Comprehend": "Comprehend",
    "Rekognition": "Rekognition",
    "Transcribe": "Transcribe",
    "Translate": "Translate",
    "Polly": "Polly",

    "SES": "SES",
    "Amazon SES": "SES",
    "Simple Email Service": "SES",

    "Pinpoint": "Pinpoint",

    # =========================================================================
    # Azure
    # =========================================================================

    "VM": "Virtual Machines",
    "VMs": "Virtual Machines",
    "Azure VM": "Virtual Machines",
    "Azure VMs": "Virtual Machines",
    "Virtual Machine": "Virtual Machines",
    "Virtual Machines": "Virtual Machines",

    "VMSS": "Virtual Machine Scale Sets",
    "Scale Set": "Virtual Machine Scale Sets",

    "AKS": "Azure Kubernetes Service",
    "Azure Kubernetes Service": "Azure Kubernetes Service",

    "ACA": "Azure Container Apps",
    "Container Apps": "Azure Container Apps",

    "ACI": "Container Instances",
    "Azure Container Instances": "Container Instances",

    "Functions": "Azure Functions",
    "Azure Functions": "Azure Functions",
    "Function App": "Azure Functions",

    "App Service": "App Service",
    "Azure App Service": "App Service",
    "Web App": "App Service",

    "Virtual Network": "Virtual Network",
    "VNet": "Virtual Network",

    "Application Gateway": "Application Gateway",
    "App Gateway": "Application Gateway",
    "AppGW": "Application Gateway",

    "Azure Load Balancer": "Azure Load Balancer",
    "Load Balancer": "Azure Load Balancer",

    "Front Door": "Azure Front Door",
    "Azure Front Door": "Azure Front Door",

    "Traffic Manager": "Traffic Manager",

    "ExpressRoute": "ExpressRoute",

    "VPN Gateway": "VPN Gateway",

    "Azure DNS": "Azure DNS",

    "CDN": "Azure CDN",
    "Azure CDN": "Azure CDN",

    "Blob": "Blob Storage",
    "Blob Storage": "Blob Storage",
    "Azure Blob Storage": "Blob Storage",

    "Azure Files": "Azure Files",

    "Managed Disk": "Disk Storage",
    "Disk Storage": "Disk Storage",

    "Queue Storage": "Queue Storage",

    "Table Storage": "Table Storage",

    "ADLS": "Data Lake Storage",
    "ADLS Gen2": "Data Lake Storage",
    "Azure Data Lake Storage": "Data Lake Storage",

    "Azure SQL": "Azure SQL Database",
    "SQL Database": "Azure SQL Database",
    "Azure SQL Database": "Azure SQL Database",

    "Managed Instance": "SQL Managed Instance",
    "SQL Managed Instance": "SQL Managed Instance",

    "Cosmos": "Cosmos DB",
    "CosmosDB": "Cosmos DB",
    "Cosmos DB": "Cosmos DB",

    "Azure PostgreSQL": "Azure Database for PostgreSQL",
    "Azure Database for PostgreSQL": "Azure Database for PostgreSQL",

    "Azure MySQL": "Azure Database for MySQL",
    "Azure Database for MySQL": "Azure Database for MySQL",

    "Azure MariaDB": "Azure Database for MariaDB",

    "Redis": "Azure Cache for Redis",
    "Redis Cache": "Azure Cache for Redis",
    "Azure Cache for Redis": "Azure Cache for Redis",

    "Synapse": "Synapse Analytics",
    "Azure Synapse": "Synapse Analytics",

    "Service Bus": "Service Bus",

    "Event Grid": "Event Grid",

    "Event Hubs": "Event Hubs",

    "Logic Apps": "Logic Apps",

    "APIM": "API Management",
    "API Management": "API Management",

    "Azure AD": "Microsoft Entra ID",
    "AAD": "Microsoft Entra ID",
    "Entra ID": "Microsoft Entra ID",
    "Microsoft Entra ID": "Microsoft Entra ID",

    "Key Vault": "Key Vault",
    "Azure Key Vault": "Key Vault",

    "Azure Firewall": "Azure Firewall",

    "Bastion": "Azure Bastion",
    "Azure Bastion": "Azure Bastion",

    "Defender for Cloud": "Microsoft Defender for Cloud",
    "Microsoft Defender for Cloud": "Microsoft Defender for Cloud",

    "DDoS Protection": "Azure DDoS Protection",

    "Azure Policy": "Azure Policy",

    "Azure Monitor": "Azure Monitor",

    "Log Analytics": "Log Analytics",

    "App Insights": "Application Insights",
    "Application Insights": "Application Insights",

    "Azure DevOps": "Azure DevOps",
    "ADO": "Azure DevOps",

    "Azure Pipelines": "Azure Pipelines",

    "Azure Repos": "Azure Repos",

    "Azure Artifacts": "Azure Artifacts",

    "ACR": "Azure Container Registry",
    "Azure Container Registry": "Azure Container Registry",

    "Bicep": "Bicep",

    "ARM": "ARM Templates",
    "ARM Template": "ARM Templates",
    "ARM Templates": "ARM Templates",

    "ADF": "Azure Data Factory",
    "Azure Data Factory": "Azure Data Factory",

    "Fabric": "Microsoft Fabric",
    "Microsoft Fabric": "Microsoft Fabric",

    "Databricks": "Databricks",
    "Azure Databricks": "Databricks",

    "Stream Analytics": "Azure Stream Analytics",

    "Azure OpenAI": "Azure OpenAI",
    "Azure OpenAI Service": "Azure OpenAI",

    "AI Foundry": "Azure AI Foundry",
    "Azure AI Foundry": "Azure AI Foundry",

    "AI Search": "Azure AI Search",
    "Azure AI Search": "Azure AI Search",
    "Cognitive Search": "Azure AI Search",
    "Azure Cognitive Search": "Azure AI Search",

    "Azure ML": "Azure Machine Learning",
    "Azure Machine Learning": "Azure Machine Learning",

    "Document Intelligence": "Document Intelligence",
    "Form Recognizer": "Document Intelligence",

    "Speech": "Speech",
    "Speech Service": "Speech",

    "Translator": "Translator",

    "Computer Vision": "Computer Vision",
    "Vision": "Computer Vision",
}