"""tests/test_main_streamlit.py

Teste de fumaça de streamlit_app/main.py (US-2.1): a navegação carrega sem
erro e a página default (upload) é executada. Rodar `pytest` a partir da
raiz do repo -- AppTest.from_file resolve o caminho relativo ao cwd.

NOTA: `streamlit.testing.v1.AppTest` não suporta `st.navigation`/`st.Page`
com paths de arquivo (limitação documentada da própria Streamlit -- ver
`streamlit/testing/v1/app_test.py`: "AppTest is not yet compatible with
multipage apps using st.navigation and st.Page"). Por isso testamos
main.py apenas quanto a não lançar exceção (a navegação e a sidebar rodam
normalmente antes de `pg.run()`, que é onde o conteúdo da página falha
silenciosamente sob AppTest -- mas funciona normalmente via `streamlit run`
real), e testamos o título da página de upload carregando-a diretamente
(sem passar pela navegação), como a própria documentação do Streamlit
recomenda para apps multipágina.
"""
from streamlit.testing.v1 import AppTest


def test_main_loads_without_exception():
    at = AppTest.from_file("streamlit_app/main.py")
    at.run()

    assert not at.exception


def test_main_sidebar_shows_offline_badge_when_no_api_running():
    at = AppTest.from_file("streamlit_app/main.py")
    at.run()

    assert not at.exception
    assert any("API indisponível" in m.value for m in at.sidebar.markdown)


def test_upload_page_loads_directly_and_shows_title():
    at = AppTest.from_file("streamlit_app/pages/01_upload.py")
    at.run()

    assert not at.exception
    assert any("Upload" in t.value for t in at.title)
