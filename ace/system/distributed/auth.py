# vim: ts=4:sw=4:et:cc=120

from typing import Optional

from ace.data_model import ErrorModel, ApiKeyResponseModel
from ace.system.distributed import app, verify_admin_api_key
from ace.system.exceptions import ACEError

from fastapi import Depends, HTTPException, Form, Response


@app.post(
    "/auth",
    responses={
        200: {"model": ApiKeyResponseModel},
        201: {"model": ApiKeyResponseModel},
        400: {"model": ErrorModel},
    },
    dependencies=[Depends(verify_admin_api_key)],
)
async def api_create_api_key(
    response: Response,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    is_admin: Optional[bool] = Form(False),
):
    try:
        result = await app.state.system.create_api_key(name, description, is_admin)
        if result:
            response.status_code = 201
            return ApiKeyResponseModel(api_key=result).dict()
        else:
            response.status_code = 200
            return ApiKeyResponseModel(api_key="").dict()

    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())


@app.delete(
    "/auth/{name}",
    responses={
        400: {"model": ErrorModel},
    },
    dependencies=[Depends(verify_admin_api_key)],
)
async def api_delete_api_key(name: str):
    try:
        result = await app.state.system.delete_api_key(name)
        if result:
            return Response(status_code=200)
        else:
            return Response(status_code=404)

    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())
