"""tests/test_streamlit_pages.py

Testes de streamlit_app/pages/01_upload.py e 02_extraction_review.py
(US-2.2, US-2.3) via streamlit.testing.v1.AppTest.

O AppTest do Streamlit não suporta simular o widget `st.file_uploader`
programaticamente -- por isso o caminho de upload real é coberto por
tests/test_api_client.py e tests/test_validation.py; aqui testamos o que o
AppTest consegue de fato simular: botões, seletores e o fluxo do diagrama
de exemplo.

Este arquivo precisa que o diretório `streamlit_app/` esteja em `sys.path`
ANTES de qualquer `unittest.mock.patch("api_client...")` -- as páginas
importam `api_client` como módulo top-level "bare" (ver bootstrap em cada
página), então o alvo do patch precisa resolver para o mesmo objeto de
módulo, não para `streamlit_app.api_client` (que seria uma cópia
importada sob outro nome e não afetaria a página).
"""
import sys
import unittest.mock
from pathlib import Path

_STREAMLIT_APP_DIR = Path(__file__).resolve().parents[1] / "streamlit_app"
if str(_STREAMLIT_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_STREAMLIT_APP_DIR))

from streamlit.testing.v1 import AppTest

from extraction.fixtures import example_diagram


def test_upload_page_example_button_populates_session_state_diagram():
    with unittest.mock.patch("streamlit.switch_page") as mock_switch_page:
        at = AppTest.from_file("streamlit_app/pages/01_upload.py")
        at.run()

        example_button = [b for b in at.button if b.label == "Usar Diagrama de Exemplo"][0]
        example_button.click().run()

        assert not at.exception
        assert at.session_state["diagram"] == example_diagram.model_dump()
        mock_switch_page.assert_called_once_with("pages/02_extraction_review.py")


def test_upload_page_example_button_resets_stale_analysis_from_previous_diagram():
    """Regressão: carregar um novo diagrama com um thread_id de uma análise
    anterior ainda em session_state não pode deixar pages/03_analysis.py
    pular direto pro resultado velho (hitl_pending/completed) em vez de
    iniciar uma análise nova."""
    with unittest.mock.patch("streamlit.switch_page") as mock_switch_page:
        at = AppTest.from_file("streamlit_app/pages/01_upload.py")
        at.run()
        at.session_state["thread_id"] = "thread-antigo"
        at.session_state["analysis_state"] = {"status": "completed", "report": {"total_components": 1}}
        at.session_state["report"] = {"total_components": 1}
        at.session_state["hitl_chat_history"] = [{"role": "user", "content": "feedback antigo"}]

        example_button = [b for b in at.button if b.label == "Usar Diagrama de Exemplo"][0]
        example_button.click().run()

        assert not at.exception
        assert at.session_state["diagram"] == example_diagram.model_dump()
        assert at.session_state["thread_id"] is None
        assert at.session_state["analysis_state"] is None
        assert at.session_state["report"] is None
        assert at.session_state["hitl_chat_history"] == []
        mock_switch_page.assert_called_once_with("pages/02_extraction_review.py")


from unittest.mock import patch


def test_extraction_review_page_renders_14_components_from_example_diagram():
    at = AppTest.from_file("streamlit_app/pages/02_extraction_review.py")
    at.session_state["diagram"] = example_diagram.model_dump()
    at.run()

    assert not at.exception
    components_df = at.dataframe[0].value
    assert len(components_df) == 14


def test_extraction_review_page_without_diagram_shows_warning():
    at = AppTest.from_file("streamlit_app/pages/02_extraction_review.py")
    at.run()

    assert len(at.warning) == 1
    assert "Nenhum diagrama" in at.warning[0].value


def test_apply_patch_success_updates_session_state_diagram():
    at = AppTest.from_file("streamlit_app/pages/02_extraction_review.py")
    at.session_state["diagram"] = example_diagram.model_dump()
    at.run()

    updated = example_diagram.model_dump()
    updated["components"][0]["name"] = "Nome corrigido"

    with patch("api_client.APIClient.apply_patch", return_value=updated):
        at.selectbox(key="patch_element_type").set_value("component").run()
        at.selectbox(key="patch_element_id").set_value(example_diagram.components[0].id).run()
        at.selectbox(key="patch_field").set_value("name").run()
        at.text_input(key="patch_value_text").set_value("Nome corrigido").run()
        apply_button = [b for b in at.button if b.label == "Aplicar Correção"][0]
        apply_button.click().run()

    assert at.session_state["diagram"]["components"][0]["name"] == "Nome corrigido"


def test_apply_patch_404_shows_api_error_message():
    from api_client import APIError

    at = AppTest.from_file("streamlit_app/pages/02_extraction_review.py")
    at.session_state["diagram"] = example_diagram.model_dump()
    at.run()

    with patch(
        "api_client.APIClient.apply_patch",
        side_effect=APIError(404, "PatchElementNotFoundError", "component 'x' não encontrado"),
    ):
        at.selectbox(key="patch_element_type").set_value("component").run()
        at.selectbox(key="patch_element_id").set_value(example_diagram.components[0].id).run()
        at.selectbox(key="patch_field").set_value("name").run()
        at.text_input(key="patch_value_text").set_value("Nome corrigido").run()
        apply_button = [b for b in at.button if b.label == "Aplicar Correção"][0]
        apply_button.click().run()

    assert len(at.error) >= 1
    assert "não encontrado" in at.error[-1].value


def test_extraction_review_page_shows_attention_marker_for_low_confidence_component():
    diagram = example_diagram.model_dump()
    diagram["components"][0]["confidence"] = 0.3
    at = AppTest.from_file("streamlit_app/pages/02_extraction_review.py")
    at.session_state["diagram"] = diagram
    at.run()

    assert not at.exception
    components_df = at.dataframe[0].value
    assert "⚠️" in components_df.iloc[0]["Atenção"]


def test_extraction_review_page_shows_attention_marker_for_data_flow_with_note():
    at = AppTest.from_file("streamlit_app/pages/02_extraction_review.py")
    at.session_state["diagram"] = example_diagram.model_dump()
    at.run()

    assert not at.exception
    data_flows_df = at.dataframe[1].value
    df8_row = data_flows_df[data_flows_df["id"] == "df-8"].iloc[0]
    assert "⚠️" in df8_row["Atenção"]


def test_extraction_review_page_shows_success_alert_for_high_confidence():
    diagram = example_diagram.model_dump()
    diagram["diagram_metadata"]["extraction_confidence"] = "alta"
    at = AppTest.from_file("streamlit_app/pages/02_extraction_review.py")
    at.session_state["diagram"] = diagram
    at.run()

    assert not at.exception
    assert len(at.success) == 1
    assert "alta" in at.success[0].value


def test_extraction_review_page_shows_warning_alert_for_medium_confidence_from_fixture():
    at = AppTest.from_file("streamlit_app/pages/02_extraction_review.py")
    at.session_state["diagram"] = example_diagram.model_dump()
    at.run()

    assert not at.exception
    assert len(at.warning) == 1
    assert "média" in at.warning[0].value


def test_analysis_page_without_diagram_shows_warning():
    at = AppTest.from_file("streamlit_app/pages/03_analysis.py")
    at.run()

    assert len(at.warning) == 1
    assert "Nenhum diagrama" in at.warning[0].value


def test_analysis_page_triggers_start_analysis_and_redirects_to_hitl_when_pending():
    response = {
        "thread_id": "thread-1",
        "status": "hitl_pending",
        "components_analyzed_count": 2,
        "components_total": 2,
        "analyzed_component_ids": ["c1", "c2"],
        "components_failed_count": 0,
        "hitl_summary": [{"component_id": "c1", "component_name": "API Gateway", "threats_count": 2}],
        "report": None,
    }
    with patch("api_client.APIClient.start_analysis", return_value=response) as mock_start, \
            patch("streamlit.switch_page") as mock_switch_page:
        at = AppTest.from_file("streamlit_app/pages/03_analysis.py")
        at.session_state["diagram"] = example_diagram.model_dump()
        at.run()

    assert not at.exception
    mock_start.assert_called_once_with(example_diagram.model_dump())
    assert at.session_state["thread_id"] == "thread-1"
    assert at.session_state["analysis_state"] == response
    mock_switch_page.assert_called_once_with("pages/04_hitl_review.py")


def test_analysis_page_redirects_to_report_when_completed_immediately():
    response = {
        "thread_id": "thread-1",
        "status": "completed",
        "components_analyzed_count": 2,
        "components_total": 2,
        "analyzed_component_ids": ["c1", "c2"],
        "components_failed_count": 0,
        "hitl_summary": None,
        "report": {"diagram_provider": "aws"},
    }
    with patch("api_client.APIClient.start_analysis", return_value=response), \
            patch("streamlit.switch_page") as mock_switch_page:
        at = AppTest.from_file("streamlit_app/pages/03_analysis.py")
        at.session_state["diagram"] = example_diagram.model_dump()
        at.run()

    assert not at.exception
    assert at.session_state["report"] == {"diagram_provider": "aws"}
    mock_switch_page.assert_called_once_with("pages/05_report.py")


def test_analysis_page_shows_error_and_retries_successfully():
    from api_client import APIError

    success_response = {
        "thread_id": "thread-1",
        "status": "hitl_pending",
        "components_analyzed_count": 2,
        "components_total": 2,
        "analyzed_component_ids": ["c1", "c2"],
        "components_failed_count": 0,
        "hitl_summary": [],
        "report": None,
    }

    with patch(
        "api_client.APIClient.start_analysis",
        side_effect=[APIError(502, "ConnectionError", "orquestração fora do ar"), success_response],
    ), patch("streamlit.switch_page") as mock_switch_page:
        at = AppTest.from_file("streamlit_app/pages/03_analysis.py")
        at.session_state["diagram"] = example_diagram.model_dump()
        at.run()

        assert not at.exception
        assert at.session_state["thread_id"] is None
        assert len(at.error) == 1
        assert "orquestração fora do ar" in at.error[0].value

        retry_button = [b for b in at.button if b.label == "Tentar novamente"][0]
        retry_button.click().run()

    assert not at.exception
    assert at.session_state["thread_id"] == "thread-1"
    mock_switch_page.assert_called_once_with("pages/04_hitl_review.py")


_HITL_PENDING_STATE = {
    "thread_id": "thread-1",
    "status": "hitl_pending",
    "components_analyzed_count": 2,
    "components_total": 2,
    "analyzed_component_ids": ["c1", "c2"],
    "components_failed_count": 0,
    "hitl_summary": [
        {"component_id": "c1", "component_name": "API Gateway", "threats_count": 2},
        {"component_id": "c2", "component_name": "RDS PostgreSQL", "threats_count": 2},
    ],
    "report": None,
}


def test_hitl_review_page_without_thread_id_shows_warning():
    at = AppTest.from_file("streamlit_app/pages/04_hitl_review.py")
    at.run()

    assert len(at.warning) == 1
    assert "Nenhuma análise" in at.warning[0].value


def test_hitl_review_page_shows_summary_table():
    at = AppTest.from_file("streamlit_app/pages/04_hitl_review.py")
    at.session_state["thread_id"] = "thread-1"
    at.session_state["analysis_state"] = _HITL_PENDING_STATE
    at.run()

    assert not at.exception
    summary_df = at.dataframe[0].value
    assert len(summary_df) == 2
    assert "4 ameaças" in at.caption[0].value


def test_hitl_review_page_chat_input_sends_refine_and_updates_summary():
    refined_state = {
        **_HITL_PENDING_STATE,
        "hitl_summary": [
            {"component_id": "c1", "component_name": "API Gateway", "threats_count": 3},
            {"component_id": "c2", "component_name": "RDS PostgreSQL", "threats_count": 2},
        ],
    }

    with patch("api_client.APIClient.send_hitl_message", return_value=refined_state) as mock_send:
        at = AppTest.from_file("streamlit_app/pages/04_hitl_review.py")
        at.session_state["thread_id"] = "thread-1"
        at.session_state["analysis_state"] = _HITL_PENDING_STATE
        at.run()

        at.chat_input[0].set_value("Revise o componente API Gateway").run()

    assert not at.exception
    mock_send.assert_called_once_with("thread-1", "refine", feedback="Revise o componente API Gateway")
    assert at.session_state["analysis_state"] == refined_state
    history = at.session_state["hitl_chat_history"]
    assert history[0] == {"role": "user", "content": "Revise o componente API Gateway"}
    assert history[1]["role"] == "assistant"
    assert "5 ameaças" in history[1]["content"]


def test_hitl_review_page_approve_button_navigates_to_report():
    completed_state = {**_HITL_PENDING_STATE, "status": "completed", "report": {"diagram_provider": "aws"}}

    with patch("api_client.APIClient.send_hitl_message", return_value=completed_state) as mock_send, \
            patch("streamlit.switch_page") as mock_switch_page:
        at = AppTest.from_file("streamlit_app/pages/04_hitl_review.py")
        at.session_state["thread_id"] = "thread-1"
        at.session_state["analysis_state"] = _HITL_PENDING_STATE
        at.run()

        approve_button = [b for b in at.button if b.label == "✅ Aprovar e Gerar Relatório"][0]
        approve_button.click().run()

    assert not at.exception
    mock_send.assert_called_once_with("thread-1", "approve")
    assert at.session_state["report"] == {"diagram_provider": "aws"}
    mock_switch_page.assert_called_once_with("pages/05_report.py")


def test_hitl_review_page_completed_status_redirects_immediately():
    completed_state = {**_HITL_PENDING_STATE, "status": "completed", "report": {"diagram_provider": "aws"}}

    with patch("streamlit.switch_page") as mock_switch_page:
        at = AppTest.from_file("streamlit_app/pages/04_hitl_review.py")
        at.session_state["thread_id"] = "thread-1"
        at.session_state["analysis_state"] = completed_state
        at.run()

    assert not at.exception
    assert at.session_state["report"] == {"diagram_provider": "aws"}
    mock_switch_page.assert_called_once_with("pages/05_report.py")


from orchestration.fixtures import example_stride_report

_REPORT_DUMP = example_stride_report().model_dump()


def test_report_page_without_report_or_thread_id_shows_warning():
    at = AppTest.from_file("streamlit_app/pages/05_report.py")
    at.run()

    assert len(at.warning) == 1
    assert "Nenhum relatório" in at.warning[0].value


def test_report_page_renders_report_from_session_state():
    at = AppTest.from_file("streamlit_app/pages/05_report.py")
    at.session_state["report"] = _REPORT_DUMP
    at.session_state["thread_id"] = "thread-1"
    at.run()

    assert not at.exception
    assert at.metric[0].value == "2"  # total_components
    assert at.metric[1].value == "4"  # total_threats
    assert any("API Gateway" in m.value for m in at.markdown)
    assert len(at.expander) == 2


def test_report_page_fetches_report_when_missing_but_thread_id_present():
    with patch("api_client.APIClient.get_report", return_value=_REPORT_DUMP) as mock_get_report:
        at = AppTest.from_file("streamlit_app/pages/05_report.py")
        at.session_state["thread_id"] = "thread-1"
        at.run()

    assert not at.exception
    mock_get_report.assert_called_once_with("thread-1")
    assert at.session_state["report"] == _REPORT_DUMP


def test_report_page_404_shows_error_with_back_button():
    from api_client import APIError

    with patch(
        "api_client.APIClient.get_report",
        side_effect=APIError(404, "NotFound", "relatório ainda não disponível"),
    ), patch("streamlit.switch_page") as mock_switch_page:
        at = AppTest.from_file("streamlit_app/pages/05_report.py")
        at.session_state["thread_id"] = "thread-1"
        at.run()

        assert len(at.error) == 1
        assert "relatório ainda não disponível" in at.error[0].value

        back_button = [b for b in at.button if b.label == "Voltar para a Revisão HITL"][0]
        back_button.click().run()

    mock_switch_page.assert_called_once_with("pages/04_hitl_review.py")


def test_report_page_nova_analise_button_resets_state_and_navigates():
    with patch("streamlit.switch_page") as mock_switch_page:
        at = AppTest.from_file("streamlit_app/pages/05_report.py")
        at.session_state["report"] = _REPORT_DUMP
        at.session_state["thread_id"] = "thread-1"
        at.session_state["diagram"] = {"components": []}
        at.run()

        nova_button = [b for b in at.button if b.label == "🔄 Nova Análise"][0]
        nova_button.click().run()

    assert at.session_state["report"] is None
    assert at.session_state["thread_id"] is None
    assert at.session_state["diagram"] is None
    mock_switch_page.assert_called_once_with("pages/01_upload.py")
