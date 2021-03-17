# vim: ts=4:sw=4:et:cc=120

from typing import Optional

from ace.data_model import ErrorModel, AlertListModel
from ace.system.distributed import app
from ace.system.exceptions import ACEError

from fastapi import Response, HTTPException, Query
from fastapi.responses import JSONResponse


@app.put(
    "/ams/{name}",
    responses={
        400: {"model": ErrorModel},
    },
)
async def api_register_alert_system(name: str):
    try:
        result = await app.state.system.register_alert_system(name)
        if result:
            return Response(status_code=201)
        else:
            return Response(status_code=200)

    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())


@app.delete(
    "/ams/{name}",
    responses={
        400: {"model": ErrorModel},
    },
)
async def api_unregister_alert_system(name: str):
    try:
        result = await app.state.system.unregister_alert_system(name)
        if result:
            return Response(status_code=200)
        else:
            return Response(status_code=404)

    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())


@app.get(
    "/ams/{name}",
    responses={
        200: {"model": AlertListModel},
        400: {"model": ErrorModel},
    },
)
async def api_get_alerts(
    name: str,
    timeout: Optional[int] = Query(None),
):
    try:
        result = await app.state.system.get_alerts(name, timeout)
        return AlertListModel(root_uuids=result).dict()
    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())
