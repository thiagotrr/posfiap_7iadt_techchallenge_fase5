"""
tests/test_logging.py

Testes do Logging Singleton (US-1.3).
"""
import logging

from app.logging_config import setup_logging


def _reset_root_logger():
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)


def test_setup_logging_adds_stream_handler_to_root():
    _reset_root_logger()

    setup_logging()

    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0], logging.StreamHandler)


def test_setup_logging_called_twice_does_not_duplicate_handlers():
    _reset_root_logger()

    setup_logging()
    setup_logging()

    root = logging.getLogger()
    assert len(root.handlers) == 1


def test_setup_logging_sets_level_from_argument():
    _reset_root_logger()

    setup_logging(level="DEBUG")

    root = logging.getLogger()
    assert root.level == logging.DEBUG


def test_setup_logging_default_level_is_info():
    _reset_root_logger()

    setup_logging()

    root = logging.getLogger()
    assert root.level == logging.INFO


def test_setup_logging_format_contains_expected_fields(capsys):
    _reset_root_logger()
    setup_logging(level="INFO")

    logging.getLogger("app.test").info("mensagem de teste")

    captured = capsys.readouterr()
    assert "[INFO]" in captured.err
    assert "app.test" in captured.err
    assert "mensagem de teste" in captured.err
    assert "—" in captured.err


def test_setup_logging_suppresses_external_libraries():
    _reset_root_logger()

    setup_logging()

    for name in ("neo4j", "httpx", "anthropic"):
        assert logging.getLogger(name).level == logging.WARNING
