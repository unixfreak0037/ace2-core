# vim: ts=4:sw=4:et:cc=120

import json
import io

from datetime import datetime
from typing import Optional, Union

from ace.data_model import ContentMetadata, ErrorModel
from ace.system.distributed import app, TAG_STORAGE

from fastapi import UploadFile, File, Form, Query, HTTPException
from fastapi.responses import StreamingResponse


@app.post(
    "/storage",
    name="Store File Content",
    responses={
        200: {"model": ContentMetadata},
        400: {"model": ErrorModel},
    },
    tags=[TAG_STORAGE],
    description="Store the given content in the storage system. Returns the ContentMetadata created for the content.",
)
async def api_store_content(
    file: UploadFile = File(..., description="The file content to store."),
    name: str = Form(..., description="The name to give the file (stored as metadata.)"),
    expiration_date: Optional[str] = Form(None, description="An optional time at which the content should expire."),
    custom: Optional[str] = Form(None, description="Optional custom data to associate to the content."),
):
    if expiration_date:
        expiration_date = datetime.fromisoformat(expiration_date)

    meta = ContentMetadata(name=name, expiration_date=expiration_date, custom=custom)

    sha256 = await app.state.system.store_content(file.file._file, meta)
    return await app.state.system.get_content_meta(sha256)


@app.get(
    "/storage/{sha256}",
    name="Get File Content",
    tags=[TAG_STORAGE],
    description="Returns the binary content of the file with the specified sha256 hash.",
)
async def api_get_content(sha256: str = Query(..., description="The sha256 hash of the content.")):
    meta = await app.state.system.get_content_meta(sha256)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Content with sha256 {sha256} not found.")

    # see https://www.starlette.io/responses/#streamingresponse
    return StreamingResponse(app.state.system.iter_content(sha256), media_type="application/octet-stream")


@app.get(
    "/storage/meta/{sha256}",
    name="Get File Content Metadata",
    responses={
        200: {"model": ContentMetadata},
    },
    tags=[TAG_STORAGE],
    description="Returns the ContentMetadata for the content with the specified sha256 hash.",
)
async def api_get_content_meta(
    sha256: str = Query(..., description="The sha256 hash of the content.")
) -> Union[ContentMetadata, None]:
    meta = await app.state.system.get_content_meta(sha256)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Content with sha256 {sha256} not found.")

    return meta
