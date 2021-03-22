# vim: ts=4:sw=4:et:cc=120

from ace.data_model import ConfigurationSetting, ErrorModel
from ace.system.exceptions import ACEError
from ace.system.distributed import app, TAG_CONFIG

from fastapi import Response, HTTPException, Query
from fastapi.responses import JSONResponse


@app.get(
    "/config",
    name="Get Configuration Setting",
    responses={
        200: {"model": ConfigurationSetting, "description": "The configuration setting is returned."},
        400: {"model": ErrorModel},
        404: {"description": "The given configuration setting does not exist."},
    },
    tags=[TAG_CONFIG],
    description="Get the value of a configuration setting.",
)
async def api_get_config(
    key: str = Query(..., description="The configuration path to acquire."),
):
    try:
        result = await app.state.system.get_config(key)
        if result is None:
            raise HTTPException(status_code=404)

        return result.dict()

    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())


@app.put(
    "/config",
    name="Set Configuration Setting",
    responses={
        201: {"description": "The configuration setting was saved."},
        400: {"model": ErrorModel},
    },
    tags=[TAG_CONFIG],
)
async def api_set_config(
    setting: ConfigurationSetting,
):
    try:
        result = await app.state.system.set_config(setting.name, setting.value, documentation=setting.documentation)
        return Response(status_code=201)

    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())


@app.delete(
    "/config",
    name="Delete Configuration Setting",
    responses={
        200: {"description": "The configuration setting was deleted."},
        400: {"model": ErrorModel},
        404: {"description": "The specified configuration setting did not exist."},
    },
    tags=[TAG_CONFIG],
)
async def api_delete_config(
    key: str = Query(..., description="The configuration path to delete."),
):
    try:
        result = await app.state.system.delete_config(key)
        if result:
            return Response(status_code=200)
        else:
            raise HTTPException(status_code=404)

    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())
