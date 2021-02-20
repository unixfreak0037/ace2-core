# vim: ts=4:sw=4:et:cc=120
# flake8: noqa

from ace.analysis import AnalysisModuleType
from ace.data_model import AnalysisModuleTypeModel, ErrorModel
from ace.system.constants import ERROR_AMT_DEP
from ace.system.distributed import app
from ace.system.exceptions import ACEError
from ace.system.analysis_module import (
    register_analysis_module_type,
    get_analysis_module_type,
)

from fastapi import Response, HTTPException
from fastapi.responses import JSONResponse


@app.post(
    "/amt",
    responses={
        200: {"model": AnalysisModuleTypeModel},
        400: {"model": ErrorModel},
    },
)
def api_register_analysis_module_type(amt: AnalysisModuleTypeModel, reponse_model=AnalysisModuleTypeModel):
    try:
        result = register_analysis_module_type(AnalysisModuleType.from_dict(amt.dict()))
        return result.to_dict()
    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=ERROR_AMT_DEP, details=str(e)).dict())


@app.get("/amt/{name}")
def api_get_analysis_module_type(name: str, response_model=AnalysisModuleTypeModel):
    amt = get_analysis_module_type(name)
    if amt is None:
        raise HTTPException(status_code=404)

    return amt.to_model()
