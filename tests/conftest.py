# tests/conftest.py
import pytest
from PyQt6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp_instance():
    app = QApplication.instance() or QApplication([])
    yield app
