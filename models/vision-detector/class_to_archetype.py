"""
Mapeamento das classes do dataset "aws-icon-detector" (Roboflow, 185 classes)
para ~15 ARQUETIPOS de arquitetura.

Serve para DUAS coisas:
  1) Colapsar as 185 classes em poucos arquetipos antes de treinar o YOLO
     (resolve o problema de ~1 imagem por classe).
  2) Ser a CHAVE da base de conhecimento STRIDE (arquetipo -> ameacas -> contramedidas).

IMPORTANTE: os nomes abaixo foram extraidos da pagina do dataset. A pagina so
mostra ~120 das 185 classes. Rode `remap_labels.py` uma vez: ele imprime todas
as classes do data.yaml que NAO estao mapeadas aqui, para voce completar em 5 min.
Nomes precisam bater EXATAMENTE com o `names:` do data.yaml (caixa e espacos).
"""

# Arquetipos que fazem sentido para modelagem de ameacas STRIDE.
ARCHETYPES = [
    "external_actor",     # entrada / fora da fronteira de confianca
    "edge_network",       # borda, DNS, roteamento, conectividade
    "load_balancer",
    "api_gateway",
    "compute",            # servidores, containers, funcoes
    "messaging_eventing", # filas, topicos, streams, eventos
    "database",
    "storage",
    "identity_access",    # IAM, diretorio, federacao
    "secrets_crypto",     # KMS, HSM, certificados
    "security_service",   # deteccao/protecao (WAF, GuardDuty, etc.)
    "logging_monitoring",
    "cicd_devops",
    "analytics_ml",
    "communication",      # email, contact center, midia
    "boundary",           # VPC/Subnet/AZ -> fronteiras de confianca (nao gera STRIDE proprio)
    "other",              # classes genericas/ruido do dataset
]

# Rotulo em PT-BR so para EXIBICAO (ex.: nome de fallback de um componente
# sem OCR legivel, ver predict.py::build_components) -- o identificador do
# arquetipo em si (chave de CLASS_TO_ARCHETYPE, nome de classe do YOLO,
# campo `category` do ArchitectureDiagram) continua em ingles de proposito:
# e compartilhado com extraction/schemas.py e outros modulos do pipeline
# (KG, LangGraph), que dependem desse valor exato.
ARCHETYPE_LABEL_PT = {
    "external_actor": "Ator Externo",
    "edge_network": "Rede de Borda",
    "load_balancer": "Balanceador de Carga",
    "api_gateway": "API Gateway",
    "compute": "Computação",
    "messaging_eventing": "Mensageria",
    "database": "Banco de Dados",
    "storage": "Armazenamento",
    "identity_access": "Identidade e Acesso",
    "secrets_crypto": "Segredos e Criptografia",
    "security_service": "Serviço de Segurança",
    "logging_monitoring": "Monitoramento e Log",
    "cicd_devops": "CI/CD",
    "analytics_ml": "Analytics e ML",
    "communication": "Comunicação",
    "boundary": "Fronteira",
    "other": "Outro",
}

# Classes estruturais que NAO sao arquetipos AWS (nao entram no mapa
# CLASS_TO_ARCHETYPE nem na base STRIDE), mas SAO objetos detectados pelo
# YOLO -- ver generate_synthetic_drawio.py, que e a unica fonte de exemplos
# rotulados para elas (o dataset Roboflow nao tem setas).
STRUCTURAL_CLASSES = ["arrowhead"]

# Sub-tipos de boundary -- 100% sintetico de proposito (ICON_GROUPS/
# PLAIN_GROUPS em generate_synthetic_drawio.py ja geram exatamente esses
# grupos com label conhecido E retangulo de verdade). O Roboflow TEM classes
# com nome parecido ("aws"=149, "Private Subnet"=111, "Public Subnet"=100,
# "Region"=30 instancias), mas sao o PICTOGRAMA pequeno de canto, nao o
# retangulo -- promove-las pra sub-tipo reintroduziria exatamente o bug que
# ja corrigimos pra "boundary" (caixa de icone e caixa de retangulo
# competindo pela MESMA classe, ensinando o detector a prever do tamanho
# errado). Ficam em "other" (EXCLUDE, ver remap_labels.py), igual antes.
# "boundary" continua existindo como classe GENERICA separada: e o fallback
# usado pelos ~12 exemplos reais anotados a mao (sem sub-tipo, so retangulo)
# e qualquer caso ambiguo -- nao foi removida nem fragmentada, so ganhou
# vizinhas mais especificas.
#
# LIMITACAO CONHECIDA: como os sub-tipos sao 100% sinteticos (nenhum
# exemplo real, nem de icone nem de retangulo anotado a mao), e bem
# provavel que sofram o MESMO gap de generalizacao pra diagramas reais que
# "boundary" sozinho sofria antes de ganhar exemplos reais anotados a mao
# (ver historico: F1 foi de ~0 ate ~0.56-0.58 so depois disso). Rotular
# alguns exemplos reais por sub-tipo (nao so retangulo generico) e o proximo
# passo natural se a generalizacao ficar fraca.
BOUNDARY_SUBTYPES = ["aws_cloud", "vpc", "region", "availability_zone", "public_subnet", "private_subnet"]

# Servicos AWS especificos com >=20 instancias reais no Roboflow
# "aws-icon-detector" (ver investigacao antes desta mudanca) -- volume
# suficiente pra tentar treinar o YOLO pra detectar o servico DIRETO em vez
# de so o arquetipo, sem cair no problema de ~1 imagem/classe que motivou
# colapsar as 185 classes originais em arquetipos (esse problema continua
# valendo pra o RESTANTE das 185 -- so promove as ~28 com dado de verdade;
# as demais continuam caindo no arquetipo, igual antes). Nomes EXATOS do
# data.yaml do Roboflow (mesma chave que CLASS_TO_ARCHETYPE).
FINE_GRAINED_SERVICES = [
    "ALB", "API-Gateway", "Aurora", "Auto Scaling Group", "Cloud Watch",
    "Cloudfront", "CodeBuild", "CodePipeline", "Cognito", "Direct Connect",
    "Dynamo DB", "EC2", "ELB", "Elastic Container Registry",
    "Elastic Container Service", "ElastiCache", "Fargate", "IAM",
    "Internet Gateway", "Kinesis Data Streams", "Lambda", "NAT Gateway",
    "RDS", "Route53", "S3", "Sagemaker", "SNS", "SQS",
]

# Classes reais que representam O MESMO servico de um FINE_GRAINED_SERVICES
# mas com nome/instancia separada no Roboflow (ex.: "IAM Role" e "IAM" sao o
# mesmo servico pra fins de deteccao) -- soma o volume de treino em vez de
# competir por espaco de feature como duas classes quase identicas.
_FINE_GRAINED_ALIASES = {
    "IAM Role": "IAM",
}

# Lista canonica e ORDEM fixa de todas as classes de deteccao do YOLO
# (arquetipos-fallback + servicos especificos + boundary/sub-tipos +
# estruturais). generate_synthetic_drawio.py e remap_labels.py usam AMBOS
# esta mesma lista/ordem para que o merge dos datasets tenha ids alinhados.
DETECTION_CLASSES = (
    sorted(a for a in ARCHETYPES if a not in ("other", "boundary"))
    + FINE_GRAINED_SERVICES
    + ["boundary"] + BOUNDARY_SUBTYPES
    + STRUCTURAL_CLASSES
)

CLASS_TO_ARCHETYPE = {
    # --- external_actor ---
    "Users": "external_actor",
    "Client": "external_actor",
    "Web Clients": "external_actor",
    "Mobile Client": "external_actor",
    "Internet": "external_actor",
    "SDK": "external_actor",
    "Alexa For Business": "external_actor",

    # --- edge_network ---
    "CDN": "edge_network",
    "Cloudfront": "edge_network",
    "Distribution": "edge_network",
    "Edge Location": "edge_network",
    "Route53": "edge_network",
    "Direct Connect": "edge_network",
    "Customer Gateway": "edge_network",
    "VPC Router": "edge_network",
    "NAT Gateway": "edge_network",
    "Internet Gateway": "edge_network",
    "Cloud Connector": "edge_network",
    "Cloud Map": "edge_network",

    # --- load_balancer ---
    "ALB": "load_balancer",
    "ELB": "load_balancer",

    # --- api_gateway ---
    "API-Gateway": "api_gateway",
    "Appsync": "api_gateway",
    "Ingress": "api_gateway",
    "Amplify": "api_gateway",

    # --- compute ---
    "EC2": "compute",
    "Lambda": "compute",
    "Fargate": "compute",
    "EKS": "compute",
    "Elastic Container Service": "compute",
    "Elastic Container Registry": "compute",
    "EMR": "compute",
    "Instances": "compute",
    "AMI": "compute",
    "Auto Scaling": "compute",
    "Auto Scaling Group": "compute",
    "Docker Image": "compute",
    "Image Builder": "compute",
    "GameLift": "compute",
    "Flask": "compute",
    "dyno": "compute",
    "cache Worker": "compute",
    "DSI": "compute",
    "fil": "compute",

    # --- messaging_eventing ---
    "SNS": "messaging_eventing",
    "SQS": "messaging_eventing",
    "MQ": "messaging_eventing",
    "Event Bus": "messaging_eventing",
    "EventBridge": "messaging_eventing",
    "Kinesis Data Streams": "messaging_eventing",
    "AppFlow": "messaging_eventing",
    "Data Pipeline": "messaging_eventing",
    "Airflow": "messaging_eventing",

    # --- database ---
    "Aurora": "database",
    "RDS": "database",
    "Dynamo DB": "database",
    "ElastiCache": "database",
    "Elastic Search": "database",
    "Athena": "database",

    # --- storage ---
    "S3": "storage",
    "EBS": "storage",
    "EFS": "storage",
    "EFS Mount Target": "storage",
    "Glacier": "storage",
    "Backup": "storage",
    "DataSync": "storage",

    # --- identity_access ---
    "IAM": "identity_access",
    "IAM Role": "identity_access",
    "Cognito": "identity_access",
    "Active Directory Service": "identity_access",
    "Control Tower": "identity_access",

    # --- secrets_crypto ---
    "Key Management Service": "secrets_crypto",
    "CloudHSM": "secrets_crypto",
    "ACM": "secrets_crypto",
    "Certificate Manager": "secrets_crypto",

    # --- security_service ---
    "GuardDuty": "security_service",
    "Inspector Agent": "security_service",
    "Detective": "security_service",
    "Firewall Manager": "security_service",
    "Config": "security_service",

    # --- logging_monitoring ---
    "Cloud Watch": "logging_monitoring",
    "CloudWatch Alarm": "logging_monitoring",
    "Cloud Trail": "logging_monitoring",
    "Flow logs": "logging_monitoring",
    "Grafana": "logging_monitoring",

    # --- cicd_devops ---
    "CodeBuild": "cicd_devops",
    "CodeCommit": "cicd_devops",
    "CodeDeploy": "cicd_devops",
    "CodePipeline": "cicd_devops",
    "CloudFormation Stack": "cicd_devops",
    "Git": "cicd_devops",
    "Github": "cicd_devops",
    "Build Environment": "cicd_devops",
    "Automated Tests": "cicd_devops",
    "Deploy Stage": "cicd_devops",
    "Fault Injection Simulator": "cicd_devops",
    "Experiments": "cicd_devops",
    "Experiment Duration": "cicd_devops",

    # --- analytics_ml ---
    "Comprehend": "analytics_ml",
    "Analytics Services": "analytics_ml",
    "Glue": "analytics_ml",
    "Glue DataBrew": "analytics_ml",
    "Cloud Search": "analytics_ml",
    "CUR": "analytics_ml",

    # --- communication ---
    "Email": "communication",
    "SES": "communication",
    "Connect": "communication",
    "Connect Contact Lens": "communication",
    "Call Metrics": "communication",
    "Call Recordings": "communication",
    "Elemental MediaConvert": "communication",
    "Elemental MediaPackage": "communication",

    # --- other (nao "boundary"!) ---
    # No dataset Roboflow "aws-icon-detector" essas 4 classes sao o PICTOGRAMA
    # pequeno (icone de canto), nao o retangulo de fronteira em si -- mediana
    # de area ~0.17% da imagem (~4%x5%), do tamanho de um icone normal, nao
    # de uma caixa que envolve varios componentes. Treinar "boundary" com
    # esses exemplos ensina o detector a prever uma caixa do tamanho do
    # icone, contradizendo os ~5900 exemplos sinteticos (generate_synthetic_
    # drawio.py) que SAO o retangulo de verdade (mediana ~18% da imagem) --
    # ver eval_against_ground_truth.py, boundary recall ficava ~0 na Figura 1
    # do enunciado. Mapeado pra "other" (descartado do treino, EXCLUDE em
    # remap_labels.py) em vez de "boundary": o dataset sintetico e a UNICA
    # fonte confiavel do conceito de retangulo de fronteira.
    "aws": "other",
    "Availability Zone": "other",
    "Public Subnet": "other",
    "VPC": "other",

    # --- other (classes genericas/placeholder do dataset) ---
    "Table": "other",
    "Container": "other",
    "Image": "other",
    "Notebook": "other",

    # --- classes extras do export Roboflow v4 (nao apareciam na pagina) ---
    # edge_network
    "Endpoint": "edge_network",
    "Network Adapter": "edge_network",
    "Private Link": "edge_network",
    "Route 53": "edge_network",
    "Transit Gateway": "edge_network",
    "VP Gateway": "edge_network",
    "VPN Connection": "edge_network",
    # compute
    "Kubernetes": "compute",
    "Quarkus": "compute",
    "Server": "compute",
    "Task Runner": "compute",
    # database
    "Memcached": "database",
    "Mongo DB": "database",
    "MySQL": "database",
    "Neptune": "database",
    "PostgreSQL": "database",
    "Redis": "database",
    "Redshift": "database",
    # storage
    "Snowball": "storage",
    "Storage Gateway": "storage",
    "Transfer Family": "storage",
    # identity_access
    "Sign-On": "identity_access",
    # secrets_crypto
    "Parameter Store": "secrets_crypto",
    "Secret Manager": "secrets_crypto",
    # security_service
    "Macie": "security_service",
    "Network Firewall": "security_service",
    "Security Group": "security_service",
    "Security Hub": "security_service",
    "Shield": "security_service",
    "WAF": "security_service",
    # logging_monitoring
    "Kibana": "logging_monitoring",
    "Organization Trail": "logging_monitoring",
    "Prometheus": "logging_monitoring",
    "Trusted Advisor": "logging_monitoring",
    "X-Ray": "logging_monitoring",
    # cicd_devops
    "Jenkins": "cicd_devops",
    "SAR": "cicd_devops",
    "SSM Agent": "cicd_devops",
    "Service Catalog": "cicd_devops",
    "Stack": "cicd_devops",
    "Systems Manager": "cicd_devops",
    "Terraform": "cicd_devops",
    # analytics_ml
    "IOT Core": "analytics_ml",
    "Lex": "analytics_ml",
    "Machine Learning": "analytics_ml",
    "Quicksight": "analytics_ml",
    "Rekognition": "analytics_ml",
    "Sagemaker": "analytics_ml",
    "Textract": "analytics_ml",
    "Transcribe": "analytics_ml",
    "Translate": "analytics_ml",
    # messaging_eventing
    "Step Function": "messaging_eventing",
    # communication
    "Pinpoint": "communication",
    "Slack": "communication",
    "Twilio": "communication",
    # api_gateway
    "SwaggerHub": "api_gateway",
    # external_actor
    "React": "external_actor",
    "Websites": "external_actor",
    # other (nao "boundary" -- pictograma pequeno no Roboflow, nao o
    # retangulo; ver comentario grande acima sobre "aws"/"VPC"/etc.)
    "Private Subnet": "other",
    "Region": "other",
    # other (sem relacao clara com arquitetura AWS)
    "Marketplace": "other",
    "Order Controller": "other",
    "Results": "other",
    "TV": "other",
    "Text File": "other",
    "VDA": "other",
}


def archetype_of(class_name: str) -> str | None:
    """Retorna o arquetipo de uma classe, ou None se nao estiver mapeada."""
    return CLASS_TO_ARCHETYPE.get(class_name)


def detection_class_of(raw_class_name: str) -> str | None:
    """Retorna a classe de DETECCAO final pra uma classe crua do Roboflow --
    o servico especifico (se estiver em FINE_GRAINED_SERVICES/aliases) ou o
    arquetipo (fallback, igual archetype_of()). Sub-tipos de boundary NAO
    tem entrada real (ver comentario em BOUNDARY_SUBTYPES) -- so o gerador
    sintetico os produz. None se a classe crua nao esta mapeada em lugar
    nenhum. Usado por remap_labels.py em vez de archetype_of() direto."""
    raw_class_name = _FINE_GRAINED_ALIASES.get(raw_class_name, raw_class_name)
    if raw_class_name in FINE_GRAINED_SERVICES:
        return raw_class_name
    return CLASS_TO_ARCHETYPE.get(raw_class_name)


# Candidatos a `aws_service` (ver extraction/README.md, limitacao "aws_service":
# o vision-detector so classifica por ARQUETIPO, nao por servico especifico --
# RDS vs. DynamoDB, por exemplo -- porque o dataset de treino nao tem
# granularidade pra isso). predict.py usa esta lista pra casar via OCR+fuzzy
# match o texto do rotulo perto de um componente detectado (ex.: "Amazon RDS"
# escrito no diagrama) contra um nome de servico real, sem precisar treinar um
# classificador de 185 classes (o problema de ~1 imagem/classe que a colapsa
# em arquetipos ja resolveu -- treinar direto nas 185 pra pegar o nome do
# servico especifico voltaria a ter esse problema).
#
# Reaproveita as chaves de CLASS_TO_ARCHETYPE (mesma fonte, ja curada) MENOS
# os termos que sao genericos/nao-especificos-de-servico, concorrentes nao-AWS
# ou lixo do dataset -- incluir esses geraria falso match (ex.: OCR ler
# "Users" no diagrama e virar aws_service="Users").
_NOT_AWS_SERVICE_NAMES = {
    # atores/conceitos genericos, nao um servico especifico
    "Users", "Client", "Web Clients", "Mobile Client", "Internet", "SDK", "Websites",
    "CDN", "Distribution", "Edge Location", "VPC Router", "Cloud Connector",
    "Endpoint", "Network Adapter", "Instances", "Docker Image", "Event Bus",
    "EFS Mount Target", "IAM Role", "Ingress", "Analytics Services", "Email",
    "Call Metrics", "Call Recordings", "Build Environment", "Automated Tests",
    "Deploy Stage", "Experiments", "Experiment Duration", "Stack",
    "Security Group",  # fica em `category` (component), nao e um aws_service
    "Machine Learning", "Organization Trail",
    # frameworks/produtos NAO-AWS que aparecem no dataset (concorrentes/OSS)
    "React", "Flask", "dyno", "Mongo DB", "MySQL", "PostgreSQL", "Redis",
    "Git", "Github", "Jenkins", "Terraform", "Slack", "Twilio", "Memcached",
    # lixo/rotulos quebrados do dataset
    "cache Worker", "DSI", "fil",
    # "other" -- ruido generico ou (VPC/Region/Subnet/AZ/aws) pictograma
    # pequeno nao-especifico, ver comentario em CLASS_TO_ARCHETYPE
    "Table", "Container", "Image", "Notebook",
    "Marketplace", "Order Controller", "Results", "TV", "Text File", "VDA",
    "aws", "Availability Zone", "Public Subnet", "Private Subnet", "Region", "VPC",
}

AWS_SERVICE_NAMES = sorted(name for name in CLASS_TO_ARCHETYPE if name not in _NOT_AWS_SERVICE_NAMES)
