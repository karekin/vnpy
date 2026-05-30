import pytest

from vnpy.web.api import tenx_hunter


def test_tenx_api_module_imports_without_multipart_dependency() -> None:
    paths = {route.path for route in tenx_hunter.router.routes}

    assert "/tenx-hunter/workspace" in paths
    assert "/tenx-hunter/deerflow/uploads" in paths


def test_deerflow_upload_endpoint_reports_missing_optional_dependency() -> None:
    if tenx_hunter._HAS_MULTIPART:
        pytest.skip("python-multipart is installed in this environment")

    with pytest.raises(tenx_hunter.HTTPException) as exc_info:
        tenx_hunter.deerflow_upload_files_unavailable(thread_id="demo")

    assert exc_info.value.status_code == 503
    assert "python-multipart" in str(exc_info.value.detail)
