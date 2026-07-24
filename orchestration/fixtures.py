"""Fixtures de exemplo do contrato de saída (para Dev 4 mockar a integração).

Publicados no Dia 2. Fornecem instâncias realistas de `STRIDEReport`,
`GraphState` e `GraphStateResponse` para o Dev 4 desenvolver o router/UI sem
depender da implementação real do grafo.

Todas as funções retornam instâncias novas (evita estado mutável compartilhado).
"""
from __future__ import annotations

from extraction.schemas import (
    ArchitectureDiagram,
    Component,
    DataFlow,
    DiagramMetadata,
    TrustBoundary,
)
from orchestration.models import (
    ComponentAnalysis,
    GraphStateResponse,
    STRIDEReport,
    STRIDEThreatEntry,
)
from orchestration.state import GraphState

_GENERATED_AT = "2026-07-15T12:00:00+00:00"


def example_diagram() -> ArchitectureDiagram:
    """Diagrama mínimo de 2 componentes (API Gateway + RDS)."""
    return ArchitectureDiagram(
        diagram_metadata=DiagramMetadata(
            cloud_provider="aws",
            region="us-east-1",
            extraction_confidence="alta",
        ),
        trust_boundaries=[
            TrustBoundary(id="tb-public", name="Public Subnet", type="subnet", parent=None),
            TrustBoundary(id="tb-private", name="Private Subnet", type="subnet", parent=None),
        ],
        components=[
            Component(
                id="c1",
                name="API Gateway",
                aws_service="Amazon API Gateway",
                element_type="process",
                category="networking",
                trust_boundary="tb-public",
                instance_count=1,
            ),
            Component(
                id="c2",
                name="RDS PostgreSQL",
                aws_service="Amazon RDS",
                element_type="data_store",
                category="database",
                trust_boundary="tb-private",
                instance_count=1,
            ),
        ],
        data_flows=[
            DataFlow(
                id="f1",
                source="c1",
                destination="c2",
                protocol="postgres/tls",
                crosses_boundary=True,
                note="Consulta de dados do usuário",
            ),
        ],
    )


def example_component_analyses() -> list[ComponentAnalysis]:
    return [
        ComponentAnalysis(
            component_id="c1",
            component_name="API Gateway",
            element_type="process",
            cloud_service="Amazon API Gateway",
            trust_boundary="tb-public",
            stride_entries=[
                # category_name é derivado automaticamente de category (validator).
                STRIDEThreatEntry(
                    category="S",
                    threat_name="Falsificação de credenciais no endpoint público",
                    threat_description=(
                        "Ator não autenticado tenta se passar por cliente legítimo "
                        "no gateway exposto à internet."
                    ),
                    severity="high",
                    mitigations=[
                        "Exigir autenticação via Cognito/JWT",
                        "Habilitar AWS WAF com rate limiting",
                    ],
                    source="both",
                ),
                STRIDEThreatEntry(
                    category="T",
                    threat_name="Adulteração de payload em trânsito",
                    threat_description="Interceptação e modificação de requisições.",
                    severity="medium",
                    mitigations=["TLS 1.2+ obrigatório", "Validação de schema do payload"],
                    source="taxonomy",
                ),
            ],
            llm_reasoning=(
                "Componente cruza trust boundary público→privado; foco em "
                "autenticação e integridade da requisição."
            ),
            analyzed_at=_GENERATED_AT,
        ),
        ComponentAnalysis(
            component_id="c2",
            component_name="RDS PostgreSQL",
            element_type="data_store",
            cloud_service="Amazon RDS",
            trust_boundary="tb-private",
            stride_entries=[
                STRIDEThreatEntry(
                    category="I",
                    threat_name="Exposição de dados sensíveis em repouso",
                    threat_description="Acesso não autorizado ao armazenamento do banco.",
                    severity="critical",
                    mitigations=[
                        "Criptografia em repouso (KMS)",
                        "Restringir security groups à subnet privada",
                    ],
                    source="both",
                ),
                STRIDEThreatEntry(
                    category="D",
                    threat_name="Exaustão de conexões do banco",
                    threat_description="Esgotamento do pool de conexões por sobrecarga.",
                    severity="high",
                    mitigations=["Connection pooling (RDS Proxy)", "Alarmes de CPU/conexões"],
                    source="enriched",
                ),
            ],
            llm_reasoning=(
                "Data store em subnet privada; risco concentrado em "
                "confidencialidade e disponibilidade."
            ),
            analyzed_at=_GENERATED_AT,
        ),
    ]


def example_stride_report() -> STRIDEReport:
    analyses = example_component_analyses()
    return STRIDEReport(
        diagram_provider="aws",
        total_components=len(analyses),
        total_threats=sum(len(a.stride_entries) for a in analyses),
        generated_at=_GENERATED_AT,
        component_analyses=analyses,
        stride_matrix={
            "S": ["c1"],
            "T": ["c1"],
            "R": [],
            "I": ["c2"],
            "D": ["c2"],
            "E": [],
        },
        risk_summary={"critical": 1, "high": 2, "medium": 1, "low": 0},
    )


def example_graph_state() -> GraphState:
    """Estado do grafo ao final de uma análise (report preenchido)."""
    diagram = example_diagram()
    analyses = {a.component_id: a for a in example_component_analyses()}
    return {
        "diagram": diagram,
        "components_queue": [],
        "current_component_id": "c2",
        "kg_results": {},
        "component_analyses": analyses,
        "chat_history": [],
        "hitl_feedback": None,
        "hitl_approved": True,
        "report": example_stride_report(),
        "error": None,
    }


def example_state_response_running() -> GraphStateResponse:
    return GraphStateResponse(
        thread_id="thread-example-0001",
        status="running",
        components_analyzed_count=1,
        components_total=2,
        analyzed_component_ids=["c1"],
        components_failed_count=0,
        hitl_summary=None,
        report=None,
    )


def example_state_response_completed() -> GraphStateResponse:
    return GraphStateResponse(
        thread_id="thread-example-0001",
        status="completed",
        components_analyzed_count=2,
        components_total=2,
        analyzed_component_ids=["c1", "c2"],
        components_failed_count=0,
        hitl_summary=None,
        report=example_stride_report(),
    )
