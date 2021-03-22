# vim: ts=4:sw=4:et:cc=120

from ace.data_model import RootAnalysisModel, ErrorModel
from ace.system.distributed import app, TAG_ANALYSIS_TRACKING
from ace.system.exceptions import ACEError

from fastapi import HTTPException, Path
from fastapi.responses import JSONResponse


@app.get(
    "/analysis_tracking/root/{uuid}",
    name="Get Root Analysis",
    responses={
        200: {
            "model": RootAnalysisModel,
            "description": "Returns the root specified by the uuid.",
        },
        400: {"model": ErrorModel},
        404: {"description": "The uuid is unknown."},
    },
    tags=[TAG_ANALYSIS_TRACKING],
    description="""Returns the root for the specified uuid.
""",
)
async def api_get_root_analysis(uuid: str = Path(..., description="The uuid of the root analysis.")):
    try:
        result = await app.state.system.get_root_analysis(uuid)
        if result:
            return result.to_dict(exclude_analysis_details=True)
        else:
            raise HTTPException(status_code=404)

    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())


@app.get(
    "/analysis_tracking/details/{uuid}",
    name="Get Analysis Details",
    responses={
        200: {
            "description": "Returns the details of the analysis specified by the uuid.",
            "content": {"application/json": {}},
        },
        400: {"model": ErrorModel},
        404: {"description": "The uuid is unknown."},
    },
    tags=[TAG_ANALYSIS_TRACKING],
    description="""Returns the details for the analysis with the specified uuid.
""",
)
async def api_get_analysis_details(uuid: str = Path(..., description="The uuid of the analysis.")):
    try:
        result = await app.state.system.get_analysis_details(uuid)
        if result:
            return result
        else:
            raise HTTPException(status_code=404)

    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())
