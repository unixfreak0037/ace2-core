# vim: ts=4:sw=4:et:cc=120
# flake8: noqa

from ace.analysis import AnalysisModuleType
from ace.data_model import AnalysisModuleTypeModel, ErrorModel
from ace.system.constants import ERROR_AMT_DEP
from ace.system.distributed import app, TAG_ANALYSIS_MODULE
from ace.system.exceptions import ACEError

from fastapi import Response, HTTPException, Path
from fastapi.responses import JSONResponse


@app.post(
    "/amt",
    responses={
        200: {"model": AnalysisModuleTypeModel, "description": "The AMT was registered to the core."},
        400: {"model": ErrorModel},
    },
    tags=[TAG_ANALYSIS_MODULE],
    name="Register Analysis Module Type",
    description="""Registers the given analysis module type to the system. If
    the module type is already registered then nothing happens.""",
)
async def api_register_analysis_module_type(amt: AnalysisModuleTypeModel):
    try:
        result = await app.state.system.register_analysis_module_type(AnalysisModuleType.from_dict(amt.dict()))
        return result.to_dict()
    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())


@app.get(
    "/amt/{name}",
    name="Get Analysis Module Type",
    responses={
        200: {"model": AnalysisModuleTypeModel},
        404: {"description": "The given type does not exist."},
    },
    tags=[TAG_ANALYSIS_MODULE],
    description="Returns the details of the given analysis module type.",
)
async def api_get_analysis_module_type(name: str = Path(..., description="The name of the analysis mode type to get.")):
    amt = await app.state.system.get_analysis_module_type(name)
    if amt is None:
        raise HTTPException(status_code=404)

    return amt.to_model()
