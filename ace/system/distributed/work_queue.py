# vim: ts=4:sw=4:et:cc=120
# flake8: noqa

from ace.data_model import AnalysisRequestModel, AnalysisRequestQueryModel, ErrorModel
from ace.system.constants import ERROR_AMT_VERSION
from ace.system.exceptions import ACEError
from ace.system.distributed import app, TAG_WORK_QUEUE

from fastapi import Response
from fastapi.responses import JSONResponse


@app.post(
    "/work_queue",
    name="Get Next Analysis Request",
    responses={
        200: {"model": AnalysisRequestModel, "description": "Returns the next observable analysis request to process."},
        204: {"description": "No work was available."},
        400: {"model": ErrorModel},
    },
    tags=[TAG_WORK_QUEUE],
    description="""Gets the next analysis request for the given analysis module type. The version of the analysis module is required, while the extended version is optional. An error occurs if the version requested does not match the version that is registered.""",
)
async def api_get_next_analysis_request(query: AnalysisRequestQueryModel):
    try:
        result = await app.state.system.get_next_analysis_request(
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
