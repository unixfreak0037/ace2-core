# vim: ts=4:sw=4:et:cc=120

from ace.data_model import ConfigurationSetting, ErrorModel
from ace.system.exceptions import ACEError
from ace.system.distributed import app

from fastapi import Response, HTTPException, Query
from fastapi.responses import JSONResponse


@app.get(
    "/config",
    responses={
        200: {"model": ConfigurationSetting},
        400: {"model": ErrorModel},
    },
)
async def api_get_config(
    key: str,
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
    responses={
        400: {"model": ErrorModel},
    },
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
    responses={
        400: {"model": ErrorModel},
    },
)
async def api_delete_config(
    key: str,
):
    try:
        result = await app.state.system.delete_config(key)
        if result:
            return Response(status_code=200)
        else:
            raise HTTPException(status_code=404)

    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())
