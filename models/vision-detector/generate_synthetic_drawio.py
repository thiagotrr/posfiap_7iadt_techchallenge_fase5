"""
Gera um dataset SINTETICO de diagramas de arquitetura AWS usando o proprio
draw.io (renderizado headless), para complementar o dataset real (Roboflow)
com exemplos que tem EXATAMENTE o estilo visual que um usuario ve ao montar
um diagrama no draw.io (mesmos icones AWS4, mesmas fontes, mesmos conectores).

Cada icone colocado no diagrama gera automaticamente seu proprio label YOLO
(classe = arquetipo, bbox = geometria do icone no XML), sem anotacao manual.
As caixas de fronteira (VPC/Subnet/AZ/...) tambem geram label (classe
"boundary", bbox = geometria da caixa) e as setas de conexao geram label da
classe estrutural "arrowhead" (bbox pequena centrada no ponto onde a seta
toca a borda do componente de destino) -- isso alimenta a deteccao de trust
boundaries e data flows no predict.py.

Requisitos no host:
    sudo snap install drawio
    sudo apt-get install -y xvfb

Uso:
    python generate_synthetic_drawio.py --n 300 --out dataset_synthetic_drawio

Depois, para treinar so com dados sinteticos, aponte train.py para
dataset_synthetic_drawio/data.yaml. Para combinar com o dataset real, copie
os splits de dataset_synthetic_drawio/ para dentro de dataset_archetypes/
(mesmos nomes de arquetipo, mesma convencao train/valid/test/images+labels).

Alem dos labels YOLO, escreve tambem `ground_truth.json` na raiz do dataset
(diagram_id -> boundaries/edges com texto e bbox originais) para conferencia
visual e para validar a heuristica de pos-processamento do predict.py contra
respostas conhecidas antes de confiar nela em diagramas reais.
"""

import argparse
import json
import random
import shutil
import subprocess
from pathlib import Path

import yaml

from class_to_archetype import DETECTION_CLASSES

# "other" e ruido/generico e continua fora do treino (ja excluido de
# DETECTION_CLASSES). "boundary" e "arrowhead" (estrutural, sem STRIDE
# proprio) sao classes de deteccao normais.
EXCLUDE = {"other"}
ALL_CLASSES = DETECTION_CLASSES
CLASS_ID = {name: i for i, name in enumerate(ALL_CLASSES)}

# Catalogo de icones AWS4 (nomes de stencil confirmados dentro do proprio
# app do draw.io, em /snap/drawio/*/resources/app.asar) por arquetipo.
# "peso" alto = arquetipos frequentes em diagramas reais (ver README).
ARCHETYPE_ICONS = {
    "external_actor": (3, ["user", "users", "mobile_client", "client", "internet", "internet_alt1"]),
    "edge_network": (1, ["cloudfront", "route_53", "internet_gateway", "nat_gateway", "direct_connect"]),
    "load_balancer": (3, ["application_load_balancer", "classic_load_balancer", "network_load_balancer"]),
    "api_gateway": (3, ["api_gateway", "appsync", "amplify"]),
    "compute": (3, ["ec2", "lambda", "fargate", "eks", "ecs", "ecs_service"]),
    "messaging_eventing": (1, ["sns", "sqs", "eventbridge", "kinesis_data_streams", "mq",
                               "kinesis_data_firehose", "managed_streaming_for_kafka",
                               "mqtt_protocol", "step_functions"]),
    "database": (3, ["aurora", "rds", "dynamodb",
                     "elasticache_for_redis", "redshift", "athena",
                     "neptune", "documentdb_with_mongodb_compatibility", "timestream"]),
    "storage": (3, ["s3", "bucket", "elastic_block_store", "efs_standard", "glacier", "backup"]),
    "identity_access": (1, ["identity_and_access_management", "cognito", "directory_service", "control_tower"]),
    "secrets_crypto": (1, ["key_management_service", "cloudhsm", "certificate_manager"]),
    "security_service": (1, ["guardduty", "inspector", "firewall_manager", "config", "waf", "shield"]),
    "logging_monitoring": (1, ["cloudwatch", "cloudtrail", "flow_logs"]),
    "cicd_devops": (1, ["codebuild", "codecommit", "codedeploy", "codepipeline", "cloudformation"]),
    "analytics_ml": (1, ["comprehend", "glue", "sagemaker", "rekognition", "cloudsearch"]),
    "communication": (1, ["connect", "email", "simple_email_service"]),
}

# Uma cor CHAPADA por arquetipo (estilo "resource icon" quadrado do AWS4;
# a cor exata nao precisa bater 100% com o guia de marca da AWS, so precisa
# ser plausivel e consistente por classe).
PALETTE = {
    "external_actor": "#232F3E",
    "edge_network": "#8C4FFF",
    "load_balancer": "#8C4FFF",
    "api_gateway": "#C7131F",
    "compute": "#C7131F",
    "messaging_eventing": "#E7157B",
    "database": "#3B48CC",
    "storage": "#60A337",
    "identity_access": "#DD344C",
    "secrets_crypto": "#DD344C",
    "security_service": "#DD344C",
    "logging_monitoring": "#E7157B",
    "cicd_devops": "#E7157B",
    "analytics_ml": "#8C4FFF",
    "communication": "#E7157B",
}

# Estencil AWS4 -> classe de deteccao ESPECIFICA (ver FINE_GRAINED_SERVICES
# em class_to_archetype.py: servicos com >=20 instancias reais no Roboflow,
# volume suficiente pra tentar treinar direto em vez de so o arquetipo).
# Estencil que nao aparece aqui continua rotulado pelo ARQUETIPO (fallback),
# igual sempre foi -- essa tabela so PROMOVE os que tem sinal real
# suficiente pra valer a pena distinguir.
ICON_TO_SERVICE = {
    "cloudfront": "Cloudfront", "route_53": "Route53",
    "internet_gateway": "Internet Gateway", "nat_gateway": "NAT Gateway",
    "direct_connect": "Direct Connect",
    "application_load_balancer": "ALB",
    "classic_load_balancer": "ELB", "network_load_balancer": "ELB",
    "api_gateway": "API-Gateway",
    "ec2": "EC2", "lambda": "Lambda", "fargate": "Fargate",
    "ecs": "Elastic Container Service", "ecs_service": "Elastic Container Service",
    "sns": "SNS", "sqs": "SQS", "kinesis_data_streams": "Kinesis Data Streams",
    "aurora": "Aurora", "rds": "RDS", "dynamodb": "Dynamo DB",
    "elasticache_for_redis": "ElastiCache",
    "s3": "S3", "bucket": "S3",
    "identity_and_access_management": "IAM", "cognito": "Cognito",
    "cloudwatch": "Cloud Watch",
    "codebuild": "CodeBuild", "codepipeline": "CodePipeline",
    "sagemaker": "Sagemaker",
}

# Grupo de fronteira (ver ICON_GROUPS/PLAIN_GROUPS abaixo) -> sub-tipo de
# boundary (ver BOUNDARY_SUBTYPES em class_to_archetype.py). Grupo sem
# sub-tipo conhecido (Security Group, Monitoring, Component -- generico
# demais ou sem volume real, ver comentario la) cai no "boundary" generico.
GROUP_TO_BOUNDARY_SUBTYPE = {
    "VPC": "vpc", "AWS Cloud": "aws_cloud", "Region": "region",
    "Availability Zone": "availability_zone",
    "Public Subnet": "public_subnet", "Private Subnet": "private_subnet",
}

ICON_MIN, ICON_MAX = 48, 76   # jitter de tamanho do icone (unidades draw.io)
MARGIN = 90
EXPORT_WIDTH_PX = 1024
ARROWHEAD_SIZE = 26  # lado (unidades draw.io) da bbox em volta do glifo endArrow=block

# Caixas de fronteira (VPC/Subnet/AZ/...): reproduzem o padrao de diagramas
# reais onde icones ficam aninhados dentro de retangulos com rotulo. Geram
# label da classe "boundary" (bbox do retangulo) e dao ao detector o mesmo
# contexto visual que ele vai ver em diagramas de verdade (ex.: a Figura 1
# do enunciado). Nesta versao as caixas nao se aninham entre si (cada uma
# agrupa um cluster de icones isolado) -- aninhamento real (ex.: Subnet
# dentro de VPC) fica para uma iteracao futura do gerador; a logica de
# containment do predict.py ja funciona com 0 ou mais niveis.
#
# Estilo extraido do proprio app.asar do draw.io (stencils reais mxgraph.aws4
# usados nos diagramas de referencia oficiais da AWS, nao inventado por nos):
# grep -ao "grIcon=mxgraph\.aws4\.group_[a-z_]*;[^\"'<]*" app.asar. VPC/Region/
# Security Group/AWS Cloud tem stencil de icone proprio; Subnet/AZ NAO tem
# (a biblioteca AWS4 nao inclui esses dois), entao usam caixa tracejada lisa
# com as cores de convencao da AWS (subnet publica=verde, privada=azul).
ICON_GROUPS = {
    "VPC": ("mxgraph.aws4.group_vpc", "#248814", 0),
    "AWS Cloud": ("mxgraph.aws4.group_aws_cloud", "#232F3E", 0),
    "Region": ("mxgraph.aws4.group_region", "#0E82B8", 1),
    "Security Group": ("mxgraph.aws4.group_security_group", "#DD3522", 0),
}
PLAIN_GROUPS = {
    "Public Subnet": "#7AA116",
    "Private Subnet": "#00A4A6",
    "Availability Zone": "#879196",
    "Monitoring": "#E7157B",
    # agrupamento logico generico sem cor/icone (preto solido fino) -- comum
    # em diagramas reais para blocos como "data ingest", "companion app", etc.
    "Component": "#232F3E",
}

# ---------------------------------------------------------------------------
# Motor de layout: TEMPLATES explicitos + posicionamento recursivo em caixas.
#
# Substitui a abordagem anterior (grid aleatorio + clusters espaciais +
# conteudo escolhido por peso probabilistico) por uma arvore de nos com
# estrutura FIXA por template, onde cada boundary contem EXATAMENTE os filhos
# definidos nela e a caixa e dimensionada para encaixar (padding fixo, sem
# folga aleatoria) -- e o padrao real observado em
# models/vision-detector/real_detection_data/exemplo_05.png: a VPC contem
# TODOS os componentes exceto Users/Internet Gateway; a Private Subnet contem
# exatamente o Auto Scaling Group + a instancia de banco primaria, nao um
# subconjunto aleatorio de icones proximos no espaco.
#
# Tres tipos de no:
#   Icon(archetype, size)            -- folha, vira 1 icone AWS4
#   Group(label, direction, children) -- boundary REAL (emite mxCell caixa +
#                                         label "boundary"/sub-tipo), filhos
#                                         empilhados em "row" ou "column"
#   Flow(direction, children)         -- container INVISIVEL (so organiza
#                                         filhos, sem caixa nem label) -- usado
#                                         para coisas como a coluna lateral de
#                                         icones soltos da Figura 1 do
#                                         enunciado, que nao tem fronteira
#                                         nenhuma ao redor.
# ---------------------------------------------------------------------------


class Icon:
    __slots__ = ("archetype", "size")

    def __init__(self, archetype, size):
        self.archetype = archetype
        self.size = size


class Group:
    __slots__ = ("label", "direction", "children", "pad", "top_pad")

    def __init__(self, label, direction, children, pad, top_pad):
        self.label = label
        self.direction = direction
        self.children = children
        self.pad = pad
        self.top_pad = top_pad


class Flow:
    __slots__ = ("direction", "children")

    def __init__(self, direction, children):
        self.direction = direction
        self.children = children


def icon(rng: random.Random, archetype: str) -> Icon:
    return Icon(archetype, rng.randint(ICON_MIN, ICON_MAX))


# Faixa de padding por instancia (sorteada UMA VEZ na construcao do Group,
# nao recalculada a cada chamada de _measure/_place -- ver comentario
# grande abaixo). Piso alto e variavel de proposito: ja tivemos esse EXATO
# bug antes (ver historico em extra_pad(), removido) -- com padding PEQUENO
# e FIXO, o detector aprende o atalho "caixa = icone do canto + deslocamento
# constante" em vez de olhar a borda/preenchimento de verdade, e a previsao
# em diagramas reais (cuja folga visual e maior e mais variavel) colapsa pro
# tamanho do icone (~48-76px, exatamente o que reapareceu quando o padding
# aqui tinha piso de so 24-56px fixo). Contencao (quais icones ficam dentro
# de qual boundary) continua 100% deterministica -- so a MARGEM ao redor do
# conteudo varia, o que alias tambem e mais realista (exemplo_05.png tem
# folga visivel, nao e "colado" no icone).
# Faixas alargadas apos o 1o retreino ainda ter saido com boundary F1 baixo
# (0.38, quase igual ao 0.39 de antes desta rodada de padding aleatorio) --
# o piso/teto de 40-110/36-150 nao estava gerando folga suficiente pra
# diferenciar "caixa" de "icone + deslocamento" com forca real. Mais perto
# da magnitude que funcionava no gerador antigo (extra_pad() ~ uniform(40,300)
# por lado, por nivel de aninhamento).
PAD_RANGE = (50, 200)
TOP_PAD_ICON_RANGE = (70, 220)   # ICON_GROUPS: topo cabe icone de canto 40x40 + label
TOP_PAD_PLAIN_RANGE = (45, 160)  # PLAIN_GROUPS: topo so precisa do texto do label
GAP = 24


def group(rng: random.Random, label: str, direction: str, children: list) -> Group:
    pad = rng.uniform(*PAD_RANGE)
    top_range = TOP_PAD_ICON_RANGE if label in ICON_GROUPS else TOP_PAD_PLAIN_RANGE
    top_pad = rng.uniform(*top_range)
    return Group(label, direction, children, pad, top_pad)


def flow(direction: str, children: list) -> Flow:
    return Flow(direction, children)


def _measure(node):
    """Retorna (w, h) da caixa que envolve `node` (icone, ou boundary/flow
    com todo o padding ja incluso). Group.pad/top_pad ja foram sorteados UMA
    VEZ na construcao (ver group() acima) -- por isso e seguro chamar
    _measure() varias vezes pro mesmo no (acontece em _place): o resultado e
    sempre o mesmo, nao redesenha um padding novo a cada chamada."""
    if isinstance(node, Icon):
        return node.size, node.size
    sizes = [_measure(c) for c in node.children]
    if node.direction == "row":
        w = sum(s[0] for s in sizes) + GAP * (len(sizes) - 1)
        h = max(s[1] for s in sizes)
    else:  # "column"
        w = max(s[0] for s in sizes)
        h = sum(s[1] for s in sizes) + GAP * (len(sizes) - 1)
    if isinstance(node, Group):
        w += 2 * node.pad
        h += node.top_pad + node.pad
    return w, h


def _place(node, x, y, icons_out, groups_out):
    """Posiciona `node` (e recursivamente seus filhos) com o canto superior
    esquerdo da sua caixa em (x, y). Preenche icons_out com
    (archetype, x, y, size) e groups_out com (x0, y0, x1, y1, label) para
    cada Group real -- Flow nunca aparece em groups_out (nao tem caixa)."""
    if isinstance(node, Icon):
        icons_out.append((node.archetype, x, y, node.size))
        return

    w, h = _measure(node)
    if isinstance(node, Group):
        top_pad, pad = node.top_pad, node.pad
        groups_out.append((x, y, x + w, y + h, node.label))
    else:
        top_pad = pad = 0

    cx0, cy0 = x + pad, y + top_pad
    cw, ch = w - 2 * pad, h - top_pad - pad
    sizes = [_measure(c) for c in node.children]
    if node.direction == "row":
        cur_x = cx0
        for child, (sw, sh) in zip(node.children, sizes):
            _place(child, cur_x, cy0 + (ch - sh) / 2, icons_out, groups_out)
            cur_x += sw + GAP
    else:
        cur_y = cy0
        for child, (sw, sh) in zip(node.children, sizes):
            _place(child, cx0 + (cw - sw) / 2, cur_y, icons_out, groups_out)
            cur_y += sh + GAP


# --- Templates ---------------------------------------------------------
# Cada template espelha a estrutura de um diagrama de referencia real (ver
# models/vision-detector/real_detection_data|real_eval_holdout). Diferente da
# versao anterior, o conteudo de cada boundary NAO e sorteado por peso: e
# definido explicitamente na propria arvore, entao "Private Subnet" sempre
# tem exatamente o que o template manda (ex.: Auto Scaling Group + banco),
# nunca um subconjunto aleatorio.

def _template_vpc_multiaz(rng: random.Random, n_az: int):
    """Espelha exemplo_05.png: AWS Cloud > (Internet Gateway direto +
    VPC) -- VPC contem TODOS os componentes exceto Users/Internet Gateway
    (ELB entre as AZs + as proprias AZs); cada AZ > Public Subnet (borda) +
    Private Subnet (o "Auto Scaling group" com a instancia de compute, e o
    banco primario/secundario direto na subnet)."""

    def az():
        asg_box = group(rng, "Component", "row", [icon(rng, "compute"), icon(rng, "compute")])
        private = group(rng, "Private Subnet", "column", [asg_box, icon(rng, "database")])
        public = group(rng, "Public Subnet", "row", [icon(rng, "edge_network"), icon(rng, "compute")])
        return group(rng, "Availability Zone", "column", [public, private])

    vpc_children = []
    for i in range(n_az):
        if i > 0:
            vpc_children.append(icon(rng, "load_balancer"))
        vpc_children.append(az())
    vpc = group(rng, "VPC", "row", vpc_children)
    cloud = group(rng, "AWS Cloud", "row", [icon(rng, "edge_network"), vpc])
    return flow("row", [icon(rng, "external_actor"), cloud])


def _template_region_fullstack(rng: random.Random, n_az: int):
    """Espelha figura1_enunciado.png/exemplo_02.png: Region > VPC > N
    Availability Zones (Public Subnet = load balancer de borda; Private
    Subnet = compute+banco+storage), mais uma coluna lateral de icones soltos
    de log/seguranca direto no AWS Cloud (fora da VPC) e uma cadeia de
    entrada (Users -> Shield -> CloudFront -> WAF) fora de tudo."""

    def az():
        # "column", nao "row": em figura1_enunciado.png a Private Subnet e
        # ALTA e ESTREITA (compute empilhado sobre 1-2 icones de banco/storage,
        # aspect ~1:3 largura:altura) porque 3 AZs dividem a largura da VPC
        # lado a lado -- "row" (3 icones lado a lado) produzia uma caixa
        # LARGA, o formato errado, e essa era a causa raiz do recall de
        # boundary ~0.09 nessa imagem especifica (caixa prevista com aspect
        # ratio incompativel nunca batia IoU>=0.5 com o retangulo real).
        lower = [icon(rng, rng.choice(["database", "storage"])) for _ in range(rng.randint(1, 2))]
        public = group(rng, "Public Subnet", "row", [icon(rng, "load_balancer")])
        private = group(rng, "Private Subnet", "column", [icon(rng, "compute"), *lower])
        return group(rng, "Availability Zone", "column", [public, private])

    vpc = group(rng, "VPC", "row", [az() for _ in range(n_az)])
    region = group(rng, "Region", "column", [vpc])
    side_pool = ["logging_monitoring", "security_service", "secrets_crypto",
                 "storage", "communication", "analytics_ml"]
    side = flow("column", [icon(rng, a) for a in rng.sample(side_pool, k=min(len(side_pool), rng.randint(2, 4)))])
    cloud = group(rng, "AWS Cloud", "row", [region, side])
    outside = flow("column", [icon(rng, "external_actor"), icon(rng, "security_service"),
                               icon(rng, "edge_network"), icon(rng, "security_service")])
    return flow("row", [outside, cloud])


def _template_logical_layers(rng: random.Random):
    """Espelha exemplo_09/exemplo_11: camadas logicas
    (ex.: API/Compute/Data) sem fronteira de rede, so agrupamento por
    proposito -- caixa generica "Component" em vez de VPC/Subnet/AZ."""
    archetype_pool = ["api_gateway", "compute", "database", "storage",
                       "messaging_eventing", "analytics_ml"]
    n_layers = rng.randint(2, 4)
    layers = []
    for _ in range(n_layers):
        n_items = rng.randint(1, 3)
        items = [icon(rng, rng.choice(archetype_pool)) for _ in range(n_items)]
        layers.append(group(rng, "Component", "row", items))
    return flow("column", layers)


def _template_flat(rng: random.Random, n_icons: int):
    """Diagrama raso, sem nenhuma boundary -- mantem no treino a diversidade
    de exemplos "simples" (poucos icones soltos), que tambem ocorrem em
    diagramas reais menores."""
    per_row = 4
    items = [icon(rng, weighted_archetype_choice(rng)) for _ in range(n_icons)]
    rows = [items[i:i + per_row] for i in range(0, len(items), per_row)]
    return flow("column", [flow("row", r) for r in rows])


TEMPLATES = [
    (_template_vpc_multiaz, 3),
    (_template_region_fullstack, 3),
    (_template_logical_layers, 2),
    (_template_flat, 2),
]

# Icones com preenchimento CHAPADO (sem gradiente): diagramas de referencia
# reais da AWS usam cor solida, nao o gradiente que usavamos antes.
# strokeColor=#ffffff fica: para esse shape (mxgraph.aws4.resourceIcon) ele
# NAO e so a borda do quadrado, e tambem a cor do glifo do icone -- sem isso
# o glifo sai preto em vez de branco (estilo real da AWS e icone branco sobre
# fundo colorido).
STYLE_TMPL = (
    "sketch=0;points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],[0,1,0],"
    "[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0],[0,0.75,0],"
    "[1,0.25,0],[1,0.5,0],[1,0.75,0]];outlineConnect=0;fontColor=#232F3E;"
    "fillColor={fill};strokeColor=#ffffff;"
    "verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;"
    "fontSize=11;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{icon};"
)


def pretty(name: str) -> str:
    return name.replace("_", " ").title()


def weighted_archetype_choice(rng: random.Random) -> str:
    names = list(ARCHETYPE_ICONS)
    weights = [ARCHETYPE_ICONS[n][0] for n in names]
    return rng.choices(names, weights=weights, k=1)[0]


def _border_point(cx: float, cy: float, size: float, dx: float, dy: float):
    """Ponto na borda de um icone quadrado (centro cx,cy, lado size) na
    direcao (dx,dy). Usado para achar onde a seta toca a caixa de destino
    (mesma regra que o draw.io usa para uma edge reta sem exitX/entryX
    fixos: clip do segmento centro-a-centro na borda do retangulo)."""
    if dx == 0 and dy == 0:
        return cx, cy
    hw = hh = size / 2
    tx = hw / abs(dx) if dx != 0 else float("inf")
    ty = hh / abs(dy) if dy != 0 else float("inf")
    t = min(tx, ty)
    return cx + t * dx, cy + t * dy


# Diagramas de referencia reais (ver models/vision-detector/real_detection_data/
# exemplo_08.png, exemplo_09.png, exemplo_07.png,
# exemplo_06.png) NAO usam so borda tracejada pra fronteira: tambem
# aparecem (a) borda SOLIDA sem preenchimento (AWS Cloud/conta/VPC em
# exemplo_07.png e exemplo_06) e (b) bloco de cor CHAPADA sem borda visivel
# nenhuma (camadas logicas tipo "API Layer"/"Data Layer"/"Web Subnet" em
# exemplo_09.png e exemplo_08.png). Sem essa variacao o detector
# via só tracejado no treino sintetico e podia aprender "boundary = borda
# tracejada" em vez do retangulo em si -- 3 estilos, sorteados por instancia
# (diagramas reais tambem misturam estilo dentro do mesmo diagrama).
#
# "AWS Cloud" e EXCECAO: em toda referencia real que revisamos (exemplo_08.png,
# exemplo_07.png, exemplo_06.png) o retangulo mais externo e
# SEMPRE borda solida cinza-escura/preta sem preenchimento, nunca tracejado
# nem colorido -- por isso e forcado, nao sorteado (ver _pick_border_style).
#
# Os outros ICON_GROUPS (VPC/Region/Security Group) tambem tem stencil de
# icone de canto nas referencias reais e SEMPRE aparecem so com contorno
# (solido ou tracejado, nunca bloco de cor) -- "filled" so ocorre nos
# PLAIN_GROUPS (Subnet/AZ/Monitoring/Component), que sao exatamente as caixas
# sem icone de canto (exemplo_08.png/exemplo_09.png).
ICON_GROUP_BORDER_STYLES = [("dashed", 1), ("solid", 1)]
PLAIN_GROUP_BORDER_STYLES = [("dashed", 5), ("solid", 3), ("filled", 3)]


def _pick_border_style(rng: random.Random, label: str) -> str:
    if label == "AWS Cloud":
        return "solid"
    choices = ICON_GROUP_BORDER_STYLES if label in ICON_GROUPS else PLAIN_GROUP_BORDER_STYLES
    names = [n for n, _ in choices]
    weights = [w for _, w in choices]
    return rng.choices(names, weights=weights, k=1)[0]


# Cor de preenchimento do estilo "filled", calibrada a partir dos pixels
# REAIS de fundo de Subnet/camada logica em exemplo_08.png e
# exemplo_09.png (amostrado via PIL): a cor real e
# um tom quase-branco (~#E6F2F8 azul, ~#E9F3E6 verde -- so uns 10-25 de
# diferenca por canal contra o branco da pagina). Bom o bastante pro olho
# humano, mas contraste baixo demais pro detector aprender o retangulo sem
# NENHUMA borda visivel (fillOpacity leve tornava a caixa quase invisivel na
# pratica). Mesma familia de tom (azul/verde), mais saturada, pra garantir
# contraste suficiente contra o fundo branco da pagina.
FILL_PALETTE = {"blue": "#B7E0F5", "green": "#C8ECC0"}
# so "Public Subnet" e verde nas referencias reais (convencao AWS: subnet
# publica = verde); todo o resto que usa "filled" (Private Subnet,
# Availability Zone, Monitoring, Component) e azul.
FILL_HUE_OF_LABEL = {"Public Subnet": "green"}


def _group_style(label: str, border: str) -> str:
    dashed = 1 if border == "dashed" else 0
    accent = PLAIN_GROUPS[label] if label not in ICON_GROUPS else ICON_GROUPS[label][1]
    # "filled" TAMBEM tem borda solida visivel, so com preenchimento por cima
    # -- conferido pixel a pixel em exemplo_08.png (coluna x=250, y~525-527): a
    # caixa "Web Subnet" tem uma linha solida azul saturada (#147EBA-ish) na
    # borda, NAO strokeColor=none como a 1a versao assumia. Sem essa linha o
    # detector so tem uma tinta muito sutil pra achar a borda do retangulo
    # (nao uma aresta de verdade), o que pode ter contribuido pra regressao
    # de boundary F1 observada no 1o retreino com esse gerador.
    if border == "filled":
        stroke, fill_color = accent, FILL_PALETTE[FILL_HUE_OF_LABEL.get(label, "blue")]
    else:
        stroke, fill_color = accent, "none"
    if label in ICON_GROUPS:
        # stencil real do AWS4 (icone no canto + borda solida/tracejada,
        # cores oficiais) -- mesma familia visual dos diagramas de
        # referencia reais da AWS. strokeWidth=3 (grosso): a borda de 1px
        # default some demais no downscale e o detector aprendia a so
        # reconhecer o icone do canto (sempre 40x40) em vez do retangulo
        # inteiro -- caixa prevista colapsava pro tamanho do icone.
        icon, _color, _default_dashed = ICON_GROUPS[label]
        return (
            f"shape=mxgraph.aws4.group;grIcon={icon};grIconSize=40;strokeWidth=3;"
            f"verticalAlign=top;align=left;spacingLeft=45;spacingTop=5;"
            f"fontColor={accent};strokeColor={stroke};dashed={dashed};fillColor={fill_color};fontSize=12;"
        )
    # Subnet/AZ/etc nao tem stencil de icone proprio no AWS4 -- caixa lisa,
    # cor de convencao da AWS, estilo de borda/preenchimento sorteado acima.
    return (
        f"rounded=0;whiteSpace=wrap;html=1;fillColor={fill_color};strokeColor={stroke};"
        f"strokeWidth=3;dashed={dashed};verticalAlign=top;align=left;fontSize=11;fontColor={accent};"
        "spacingLeft=6;spacingTop=4;"
    )


def build_diagram(rng: random.Random, diagram_id: str, n_icons: int):
    """Retorna (xml_str, labels, meta): labels e lista de 'class_id cx cy w h'
    (normalizado, formato YOLO); meta traz boundaries/edges com texto e bbox
    originais (nao normalizados p/ treino, so para conferencia/avaliacao)."""
    # Escolhe um template (arvore Icon/Group/Flow fixa, ver TEMPLATES acima) e
    # posiciona com o motor recursivo _place -- cada boundary sai com
    # EXATAMENTE os filhos definidos no template, caixa dimensionada por
    # padding fixo (sem folga aleatoria), reproduzindo o padrao "VPC contem
    # tudo exceto Users/Internet Gateway; Private Subnet contem exatamente o
    # Auto Scaling Group + o banco primario" observado em exemplo_05.png.
    names = [t for t, _ in TEMPLATES]
    weights = [w for _, w in TEMPLATES]
    template = rng.choices(names, weights=weights, k=1)[0]
    n_az = min(3, max(1, round(n_icons / 6)))
    if template is _template_flat:
        root = template(rng, n_icons)
    elif template is _template_logical_layers:
        root = template(rng)
    else:
        root = template(rng, n_az)

    icons_out = []  # (archetype, x, y, size), na ordem de percurso da arvore
    groups_meta = []  # (x0, y0, x1, y1, label) -- so Group emite entrada aqui
    _place(root, MARGIN, MARGIN, icons_out, groups_meta)

    # cada icone da arvore ja chega com arquetipo FIXO (definido no proprio
    # template, nao sorteado por peso de conteudo depois) -- so falta band a
    # stencil concreto (ARCHETYPE_ICONS) e a classe de deteccao final.
    icon_of = {}  # cell_id -> nome do stencil AWS4
    label_class_of = {}  # cell_id -> classe de deteccao final (servico especifico ou arquetipo)
    placed = []  # (cell_id, archetype, x, y, size)
    for i, (archetype, x, y, size) in enumerate(icons_out):
        cell_id = f"n{i}"
        icon_name = rng.choice(ARCHETYPE_ICONS[archetype][1])
        icon_of[cell_id] = icon_name
        label_class_of[cell_id] = ICON_TO_SERVICE.get(icon_name, archetype)
        placed.append((cell_id, archetype, x, y, size))

    # o motor de layout so soma paddings/gaps positivos a partir de (MARGIN,
    # MARGIN), entao x/y nunca deveriam ficar negativos -- mantido como rede
    # de seguranca barata (o bug real de overflow, corrigido antes, vinha do
    # gerador anterior por cluster+padding aleatorio).
    min_x = min([x for _, _, x, y, _ in placed] + [g[0] for g in groups_meta] + [0])
    min_y = min([y for _, _, x, y, _ in placed] + [g[1] for g in groups_meta] + [0])
    if min_x < 0 or min_y < 0:
        shift_x, shift_y = -min(min_x, 0), -min(min_y, 0)
        placed = [(cid, arch, x + shift_x, y + shift_y, size) for cid, arch, x, y, size in placed]
        groups_meta = [
            (x0 + shift_x, y0 + shift_y, x1 + shift_x, y1 + shift_y, label)
            for x0, y0, x1, y1, label in groups_meta
        ]

    cells_xml = [
        f'<mxCell id="{cid}" value="{pretty(icon_of[cid])}" '
        f'style="{STYLE_TMPL.format(fill=PALETTE[arch], icon=icon_of[cid])}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{size}" height="{size}" as="geometry" /></mxCell>'
        for cid, arch, x, y, size in placed
    ]
    groups_xml = [
        f'<mxCell id="g{i}" value="{label}" style="{_group_style(label, _pick_border_style(rng, label))}" '
        f'vertex="1" parent="1">'
        f'<mxGeometry x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" as="geometry" /></mxCell>'
        for i, (x0, y0, x1, y1, label) in enumerate(groups_meta)
    ]

    # conecta alguns pares consecutivos com setas. Estilo reto (sem
    # orthogonalEdgeStyle) de proposito: assim a posicao da seta na borda do
    # destino e calculavel analiticamente (_border_point), sem precisar
    # parsear o roteamento renderizado pelo draw.io. E uma simplificacao do
    # DADO DE TREINO, nao da inferencia -- o detector aprende a forma local
    # do glifo da seta, que aparece igual em diagramas reais com roteamento
    # ortogonal.
    edges_xml = []
    edges_meta = []  # (src_idx, dst_idx, arrow_x, arrow_y)
    for i in range(len(placed) - 1):
        if rng.random() < 0.5:  # diagramas reais sao bem conectados (ver Figura 1)
            src_idx, dst_idx = i, i + 1
            src_id, dst_id = placed[src_idx][0], placed[dst_idx][0]
            # metade das setas tracejada: diagramas reais usam MUITO conector
            # tracejado (ver Figura 1 do enunciado) e o detector nunca via
            # isso -- so tinha exemplo de seta solida no treino.
            dashed = 1 if rng.random() < 0.5 else 0
            edges_xml.append(
                f'<mxCell id="e{i}" style="rounded=0;html=1;endArrow=block;dashed={dashed};'
                f'strokeColor=#545B64;" edge="1" parent="1" source="{src_id}" target="{dst_id}">'
                '<mxGeometry relative="1" as="geometry" /></mxCell>'
            )
            _, _, sx, sy, ssize = placed[src_idx]
            _, _, tx, ty, tsize = placed[dst_idx]
            scx, scy = sx + ssize / 2, sy + ssize / 2
            tcx, tcy = tx + tsize / 2, ty + tsize / 2
            ax, ay = _border_point(tcx, tcy, tsize, scx - tcx, scy - tcy)
            edges_meta.append((src_idx, dst_idx, ax, ay))

    # pagina cobre o bbox dos icones + a folga do MARGIN ao redor, OU o bbox
    # das caixas de grupo se elas extrapolarem isso (cadeias de aninhamento
    # profundo somam varias camadas de padding e podem passar do MARGIN).
    page_w = max([x + size + MARGIN for _, _, x, y, size in placed], default=800)
    page_h = max([y + size + MARGIN for _, _, x, y, size in placed], default=600)
    if groups_meta:
        page_w = max(page_w, max(x1 for _, _, x1, _, _ in groups_meta) + 20)
        page_h = max(page_h, max(y1 for _, _, _, y1, _ in groups_meta) + 20)

    # Diagramas reais raramente sao croppados justo como o nosso -- costumam
    # ter bastante espaco em branco ao redor do conteudo (ver Figura 1 do
    # enunciado). Sem essa variacao o modelo so aprende a reconhecer objetos
    # (principalmente setas, que ja sao a classe menor) na escala "cropada
    # justo", e erra a escala quando o diagrama real tem folga -- foi
    # exatamente essa a causa raiz de setas nao serem detectadas na Figura 1.
    page_w *= rng.uniform(1.0, 1.5)
    page_h *= rng.uniform(1.0, 1.4)

    # retangulo invisivel do tamanho da pagina inteira: forca o crop do export
    # a sempre cobrir (0,0)-(page_w,page_h), assim o mapeamento
    # unidade-de-diagrama -> pixel vira uma escala fixa e conhecida.
    anchor = (
        f'<mxCell id="anchor" style="fillColor=none;strokeColor=none;" vertex="1" parent="1">'
        f'<mxGeometry x="0" y="0" width="{page_w}" height="{page_h}" as="geometry" /></mxCell>'
    )

    xml = (
        '<mxfile host="app.diagrams.net"><diagram name="Page-1">'
        f'<mxGraphModel dx="800" dy="600" grid="0" gridSize="10" guides="1" tooltips="1" connect="1" '
        f'arrows="1" fold="1" page="1" pageScale="1" pageWidth="{page_w}" pageHeight="{page_h}" math="0" shadow="0">'
        f'<root><mxCell id="0" /><mxCell id="1" parent="0" />{anchor}'
        + "".join(groups_xml) + "".join(cells_xml) + "".join(edges_xml) +
        "</root></mxGraphModel></diagram></mxfile>"
    )

    scale = EXPORT_WIDTH_PX / page_w
    img_h = round(page_h * scale)

    def to_norm_box(x0, y0, x1, y1):
        cx = (x0 + (x1 - x0) / 2) * scale / EXPORT_WIDTH_PX
        cy = (y0 + (y1 - y0) / 2) * scale / img_h
        w = (x1 - x0) * scale / EXPORT_WIDTH_PX
        h = (y1 - y0) * scale / img_h
        return cx, cy, w, h

    labels = []
    for cell_id, archetype, x, y, size in placed:
        if archetype in EXCLUDE:
            continue
        cx, cy, w, h = to_norm_box(x, y, x + size, y + size)
        label_class = label_class_of[cell_id]
        labels.append(f"{CLASS_ID[label_class]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

    for x0, y0, x1, y1, group_label in groups_meta:
        cx, cy, w, h = to_norm_box(x0, y0, x1, y1)
        boundary_class = GROUP_TO_BOUNDARY_SUBTYPE.get(group_label, "boundary")
        labels.append(f"{CLASS_ID[boundary_class]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

    for _src_idx, _dst_idx, ax, ay in edges_meta:
        half = ARROWHEAD_SIZE / 2
        cx, cy, w, h = to_norm_box(ax - half, ay - half, ax + half, ay + half)
        labels.append(f"{CLASS_ID['arrowhead']} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

    meta = {
        "boundaries": [
            {"label": label, "bbox_norm": list(to_norm_box(x0, y0, x1, y1))}
            for x0, y0, x1, y1, label in groups_meta
        ],
        "edges": [
            {
                "source_archetype": placed[src_idx][1],
                "dest_archetype": placed[dst_idx][1],
                "arrowhead_norm": [ax * scale / EXPORT_WIDTH_PX, ay * scale / img_h],
            }
            for src_idx, dst_idx, ax, ay in edges_meta
        ],
    }

    return xml, labels, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300, help="numero de diagramas sinteticos")
    ap.add_argument("--out", default="dataset_synthetic_drawio")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-icons", type=int, default=4)
    ap.add_argument("--max-icons", type=int, default=20)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out = Path(args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    src_dir = out / "_drawio_src"
    src_dir.mkdir(parents=True)

    split_of = {}
    all_labels = {}
    all_meta = {}
    for i in range(args.n):
        diagram_id = f"synth_{i:05d}"
        n_icons = rng.randint(args.min_icons, args.max_icons)
        xml, labels, meta = build_diagram(rng, diagram_id, n_icons)
        (src_dir / f"{diagram_id}.drawio").write_text(xml, encoding="utf-8")
        all_labels[diagram_id] = labels
        all_meta[diagram_id] = meta
        r = rng.random()
        split_of[diagram_id] = "train" if r < 0.8 else ("valid" if r < 0.9 else "test")

    print(f"Gerados {args.n} diagramas .drawio em {src_dir}. Renderizando com draw.io headless...")
    subprocess.run(
        [
            "xvfb-run", "-a", "drawio", "--export", "--format", "png",
            "--width", str(EXPORT_WIDTH_PX), "--output", str(src_dir),
            str(src_dir),
        ],
        check=True,
    )

    for split in ("train", "valid", "test"):
        (out / split / "images").mkdir(parents=True, exist_ok=True)
        (out / split / "labels").mkdir(parents=True, exist_ok=True)

    for diagram_id, labels in all_labels.items():
        split = split_of[diagram_id]
        png_src = src_dir / f"{diagram_id}.png"
        if not png_src.exists():
            print(f"AVISO: {png_src.name} nao foi gerado, pulando.")
            continue
        shutil.move(str(png_src), out / split / "images" / f"{diagram_id}.png")
        (out / split / "labels" / f"{diagram_id}.txt").write_text("\n".join(labels), encoding="utf-8")

    shutil.rmtree(src_dir)

    data_yaml = {
        "train": "train/images",
        "val": "valid/images",
        "test": "test/images",
        "nc": len(ALL_CLASSES),
        "names": ALL_CLASSES,
    }
    (out / "data.yaml").write_text(yaml.safe_dump(data_yaml, sort_keys=False), encoding="utf-8")

    (out / "ground_truth.json").write_text(
        json.dumps(all_meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"OK. Dataset sintetico em {out}/data.yaml ({len(ALL_CLASSES)} classes, {args.n} diagramas)")


if __name__ == "__main__":
    main()
