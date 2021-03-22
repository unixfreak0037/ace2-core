# vim: ts=4:sw=4:et:cc=120

from typing import Optional

from ace.data_model import ErrorModel, ApiKeyResponseModel
from ace.system.distributed import app, verify_admin_api_key, TAG_AUTH
from ace.system.exceptions import ACEError

from fastapi import Depends, HTTPException, Form, Response, Path
from fastapi.responses import JSONResponse


@app.post(
    "/auth",
    name="Create API Key",
    responses={
        200: {
            "model": ApiKeyResponseModel,
            "description": "The API key was **already** created. In this case the api_key field in the response is empty.",
        },
        201: {"model": ApiKeyResponseModel, "description": "The API key was created."},
        400: {"model": ErrorModel},
    },
    tags=[TAG_AUTH],
    dependencies=[Depends(verify_admin_api_key)],
    description="""Creates a new api key.

Api keys are required to access any api function remotely. Each api key has a
unique name and an optional description.

Some api calls require admin level api keys. An admin api key can be created by
setting the is_admin optional parameter to True.

Returns the value of the randomly generated api key. This value must be kept
secret and cannot be recovered. If an api key is lost, you must delete the api
key and re-create it.
""",
)
async def api_create_api_key(
    response: Response,
    name: str = Form(..., description="The name of the API key. The name must be unique."),
    description: Optional[str] = Form(
        None, description="An optional description that adds additional context to an api key."
    ),
    is_admin: Optional[bool] = Form(
        False, description="Set this to True to create an admin-level api key. Defaults to a standard api key."
    ),
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
    name="Delete API Key",
    responses={
        200: {"description": "The API key was deleted."},
        400: {"model": ErrorModel},
        404: {"description": "The specified API key was invalid."},
    },
    tags=[TAG_AUTH],
    dependencies=[Depends(verify_admin_api_key)],
    description="Deletes the given api key from the system.",
)
async def api_delete_api_key(name: str = Path(..., description="The name of the api key to delete.")):
    try:
        result = await app.state.system.delete_api_key(name)
        if result:
            return Response(status_code=200)
        else:
            return Response(status_code=404)

    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())
