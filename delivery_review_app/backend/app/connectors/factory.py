from app.connectors.base import PlatformConnector
from app.connectors.mock_connector import MockConnector


def get_connector(platform: str) -> PlatformConnector:
    # TODO: replace platform-specific real API connectors
    return MockConnector()
