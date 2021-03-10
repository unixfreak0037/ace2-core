# vim: ts=4:sw=4:et:cc=120

from ace.data_model import AnalysisRequestModel, ErrorModel
from ace.system.analysis_request import AnalysisRequest
from ace.system.distributed import app
from ace.system.exceptions import ACEError

from fastapi import Response
from fastapi.responses import JSONResponse


@app.post(
    "/process_request",
    responses={
        400: {"model": ErrorModel},
    },
)
async def api_process_analysis_request(request: AnalysisRequestModel):
    try:
        await app.state.system.process_analysis_request(AnalysisRequest.from_dict(request.dict(), app.state.system))
    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)))
