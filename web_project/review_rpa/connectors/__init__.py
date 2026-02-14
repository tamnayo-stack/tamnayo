from connectors.unified import UnifiedReviewConnector


def get_connector_class(_platform_name: str):
    """요청사항: 플랫폼별 개별 파일 대신 단일 통합 커넥터 사용."""
    return UnifiedReviewConnector
