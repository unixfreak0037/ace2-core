# vim: ts=4:sw=4:et:cc=120
# flake8: noqa

from ace.data_model import AnalysisRequestModel, AnalysisRequestQueryModel, ErrorModel
from ace.system.constants import ERROR_AMT_VERSION
from ace.system.exceptions import ACEError
from ace.system.distributed import app
from ace.system.work_queue import get_next_analysis_request

from fastapi import Response
from fastapi.responses import JSONResponse


@app.post(
    "/work_queue",
    responses={
        200: {"model": AnalysisRequestModel},
        400: {"model": ErrorModel},
    },
)
def api_get_next_analysis_request(query: AnalysisRequestQueryModel):
    try:
        result = get_next_analysis_request(
            query.owner,
            query.amt,
            timeout=query.timeout,
            version=query.version,
            extended_version=query.extended_version,
        )
    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())

    if not result:
        return Response(status_code=204)

    return result.to_model()
