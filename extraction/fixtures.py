"""Fixture de teste: um `ArchitectureDiagram` válido para outros devs mocarem
a saída do extrator sem depender da implementação real.

Este é o diagrama de referência canônico do projeto (14 componentes, 14 data
flows, 3-tier web app AWS), compartilhado pelo time via
`json-referência_arquitetura.json`. Uma correção foi aplicada em relação ao
JSON original: `comp-rds-standby` referenciava `tb-az2-implicita` sem essa
trust boundary estar declarada em `trust_boundaries` (violava a integridade
referencial validada em `extraction/schemas.py`) — a boundary implícita foi
declarada explicitamente abaixo, mantendo o mesmo id.

Uso:
    from extraction.fixtures import example_diagram
"""

from extraction.schemas import ArchitectureDiagram, DiagramPatch

_RAW = {
    "diagram_metadata": {
        "cloud_provider": "AWS",
        "region": "não explicitado no diagrama",
        "extraction_confidence": "média - contém ambiguidades a validar via HITL",
    },
    "trust_boundaries": [
        {"id": "tb-internet", "name": "Internet / Cliente", "type": "public"},
        {"id": "tb-cdn-edge", "name": "Edge CloudFront (static content)", "type": "public_edge"},
        {"id": "tb-region", "name": "AWS Region", "type": "region"},
        {"id": "tb-az1", "name": "Availability Zone AZ-1", "type": "availability_zone", "parent": "tb-region"},
        # Nao estava no JSON original (so referenciada por comp-rds-standby,
        # sem declaracao) -- adicionada para nao violar integridade referencial.
        {"id": "tb-az2-implicita", "name": "Availability Zone AZ-2 (implícita)",
         "type": "availability_zone", "parent": "tb-region"},
    ],
    "components": [
        {"id": "comp-user", "name": "Usuário/Cliente", "aws_service": None,
         "element_type": "external_entity", "trust_boundary": "tb-internet"},
        {"id": "comp-route53", "name": "Route 53 Hosted Zone", "aws_service": "Route53",
         "element_type": "process", "category": "dns", "trust_boundary": "tb-region"},
        {"id": "comp-elb", "name": "Elastic Load Balancer", "aws_service": "ELB",
         "element_type": "process", "category": "load_balancing", "trust_boundary": "tb-region"},
        {"id": "comp-web-asg", "name": "Web Servers (Auto Scaling Group)", "aws_service": "EC2",
         "element_type": "process", "category": "compute_web_tier",
         "trust_boundary": "tb-az1", "instance_count": 2},
        {"id": "comp-app-tier", "name": "App Servers", "aws_service": "EC2",
         "element_type": "process", "category": "compute_app_tier",
         "trust_boundary": "tb-az1", "instance_count": 2},
        {"id": "comp-elasticache", "name": "ElastiCache Tier", "aws_service": "ElastiCache",
         "element_type": "data_store", "category": "cache", "trust_boundary": "tb-az1"},
        {"id": "comp-rds-master", "name": "RDS (Master)", "aws_service": "RDS",
         "element_type": "data_store", "category": "relational_db", "trust_boundary": "tb-az1"},
        {"id": "comp-rds-standby", "name": "RDS (Standby Multi-AZ)", "aws_service": "RDS",
         "element_type": "data_store", "category": "relational_db_replica",
         "trust_boundary": "tb-az2-implicita"},
        {"id": "comp-s3", "name": "S3 Bucket", "aws_service": "S3",
         "element_type": "data_store", "category": "object_storage", "trust_boundary": "tb-region"},
        {"id": "comp-cloudfront", "name": "CloudFront", "aws_service": "CloudFront",
         "element_type": "process", "category": "cdn", "trust_boundary": "tb-cdn-edge"},
        {"id": "comp-cloudwatch", "name": "CloudWatch Alarms", "aws_service": "CloudWatch",
         "element_type": "process", "category": "monitoring", "trust_boundary": "tb-region"},
        {"id": "comp-sns", "name": "SNS Notifications", "aws_service": "SNS",
         "element_type": "process", "category": "messaging", "trust_boundary": "tb-region"},
        {"id": "comp-dynamodb", "name": "DynamoDB Tables", "aws_service": "DynamoDB",
         "element_type": "data_store", "category": "nosql_db", "trust_boundary": "tb-region"},
        {"id": "comp-ses", "name": "SES Email", "aws_service": "SES",
         "element_type": "process", "category": "email", "trust_boundary": "tb-region"},
    ],
    "data_flows": [
        {"id": "df-1", "source": "comp-user", "destination": "comp-route53",
         "protocol": "DNS", "crosses_boundary": True},
        {"id": "df-2", "source": "comp-route53", "destination": "comp-elb",
         "protocol": "HTTPS", "crosses_boundary": False},
        {"id": "df-3", "source": "comp-elb", "destination": "comp-web-asg",
         "protocol": "HTTPS", "crosses_boundary": True},
        {"id": "df-4", "source": "comp-web-asg", "destination": "comp-app-tier",
         "protocol": "HTTP interno", "crosses_boundary": False},
        {"id": "df-5", "source": "comp-app-tier", "destination": "comp-elasticache",
         "protocol": "Redis/Memcached", "crosses_boundary": False},
        {"id": "df-6", "source": "comp-app-tier", "destination": "comp-rds-master",
         "protocol": "SQL/TCP", "crosses_boundary": False},
        {"id": "df-7", "source": "comp-rds-master", "destination": "comp-rds-standby",
         "protocol": "replicação síncrona", "crosses_boundary": True, "note": "failover Multi-AZ"},
        {"id": "df-8", "source": "comp-web-asg", "destination": "comp-s3",
         "protocol": "HTTPS/REST", "crosses_boundary": True,
         "note": "rotulado 'AZ' no diagrama - ambíguo, validar via HITL"},
        {"id": "df-9", "source": "comp-s3", "destination": "comp-cloudfront",
         "protocol": "HTTPS (origin pull)", "crosses_boundary": True},
        {"id": "df-10", "source": "comp-cloudfront", "destination": "comp-user",
         "protocol": "HTTPS", "crosses_boundary": True, "note": "media.yourApp.com"},
        {"id": "df-11", "source": "comp-elb", "destination": "comp-cloudwatch",
         "protocol": "API métricas", "crosses_boundary": False},
        {"id": "df-12", "source": "comp-app-tier", "destination": "comp-sns",
         "protocol": "API", "crosses_boundary": False, "note": "origem exata ambígua no desenho"},
        {"id": "df-13", "source": "comp-app-tier", "destination": "comp-dynamodb",
         "protocol": "API", "crosses_boundary": False, "note": "origem exata ambígua no desenho"},
        {"id": "df-14", "source": "comp-app-tier", "destination": "comp-ses",
         "protocol": "API/SMTP", "crosses_boundary": False, "note": "origem exata ambígua no desenho"},
    ],
}

example_diagram: ArchitectureDiagram = ArchitectureDiagram.model_validate(_RAW)


# Exemplo de DiagramPatch cobrindo as três operações suportadas (ver
# extraction/schemas.py::ElementPatch). Aplicado em sequência via
# extraction.service.apply_patch(example_diagram, example_patch):
#   1. update — corrige o element_type de comp-cloudwatch (o vision-detector
#      classificou como "process" quando na verdade é o monitoramento, ok,
#      mas aqui simula uma correção humana comum: arquétipo certo, STRIDE
#      element_type errado).
#   2. add — adiciona um componente que o extrator não detectou (falso
#      negativo), caso dominante de erro num pipeline de detecção de objetos.
#   3. update + remove — reatribui comp-rds-standby para tb-az1 e então
#      remove a trust boundary tb-az2-implicita (falso positivo, ex.:
#      retângulo traçado por engano a partir de uma borda vizinha). A
#      reatribuição precisa vir antes do remove: patches são aplicados em
#      ordem, e removê-la primeiro deixaria comp-rds-standby apontando para
#      uma trust_boundary inexistente até o resto do patch ser aplicado —
#      inofensivo aqui porque a validação de integridade referencial roda
#      uma única vez, no final de todo o DiagramPatch (ver apply_patch em
#      extraction/service.py), não a cada patch individual.
example_patch: DiagramPatch = DiagramPatch.model_validate({
    "patches": [
        {
            "op": "update",
            "element_type": "component",
            "element_id": "comp-cloudwatch",
            "field": "element_type",
            "value": "data_store",
        },
        {
            "op": "add",
            "element_type": "component",
            "value": {
                "id": "comp-nat-gateway",
                "name": "NAT Gateway",
                "aws_service": None,
                "element_type": "process",
                "category": "networking",
                "trust_boundary": "tb-az1",
            },
        },
        {
            "op": "update",
            "element_type": "component",
            "element_id": "comp-rds-standby",
            "field": "trust_boundary",
            "value": "tb-az1",
        },
        {
            "op": "remove",
            "element_type": "trust_boundary",
            "element_id": "tb-az2-implicita",
            "field": None,
        },
    ],
})
