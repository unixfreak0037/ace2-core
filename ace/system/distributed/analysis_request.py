# vim: ts=4:sw=4:et:cc=120

from ace.data_model import AnalysisRequestModel, ErrorModel
from ace.system.analysis_request import AnalysisRequest
from ace.system.distributed import app, TAG_ANALYSIS_REQUEST
from ace.system.exceptions import ACEError

from fastapi import Response
from fastapi.responses import JSONResponse


@app.post(
    "/process_request",
    name="Process Analysis Request",
    responses={
        200: {"description": "The request was successfully processed."},
        400: {"model": ErrorModel},
    },
    tags=[TAG_ANALYSIS_REQUEST],
    description="""Process the given analysis request. Returns a 200 if the request was successfully processed.""",
)
async def api_process_analysis_request(request: AnalysisRequestModel):
    try:
        await app.state.system.process_analysis_request(AnalysisRequest.from_dict(request.dict(), app.state.system))
        return Response(status_code=200)
    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())
