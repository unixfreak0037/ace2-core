# vim: ts=4:sw=4:et:cc=120

import json
import io

from datetime import datetime
from typing import Optional, Union

from ace.data_model import ContentMetadata, ErrorModel
from ace.system.distributed import app

from fastapi import UploadFile, File, Form, Query, HTTPException
from fastapi.responses import StreamingResponse


@app.post(
    "/storage",
    responses={
        200: {"model": ContentMetadata},
        400: {"model": ErrorModel},
    },
)
async def api_store_content(
    file: UploadFile = File(...),
    name: str = Form(...),
    expiration_date: Optional[str] = Form(None),
    custom: Optional[str] = Form({}),
):

    if expiration_date:
        expiration_date = datetime.fromisoformat(expiration_date)

    if custom:
        custom = json.loads(custom)

    meta = ContentMetadata(name=name, expiration_date=expiration_date, custom=custom)

    sha256 = await app.state.system.store_content(file.file._file, meta)
    return await app.state.system.get_content_meta(sha256)


@app.get("/storage/{sha256}")
async def api_get_content(sha256: str = Query(...)):
    meta = await app.state.system.get_content_meta(sha256)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Content with sha256 {sha256} not found.")

    # async def _reader(sha256: str):
    # with await app.state.system.get_content_stream(sha256) as fp:
    # while True:
    # chunk = fp.read(io.DEFAULT_BUFFER_SIZE)
    # if chunk == b"":
    # break

    # yield chunk

    # see https://www.starlette.io/responses/#streamingresponse
    return StreamingResponse(app.state.system.iter_content(sha256), media_type="application/octet-stream")


@app.get(
    "/storage/meta/{sha256}",
    responses={
        200: {"model": ContentMetadata},
    },
)
async def api_get_content_meta(sha256: str = Query(...)) -> Union[ContentMetadata, None]:
    meta = await app.state.system.get_content_meta(sha256)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Content with sha256 {sha256} not found.")

    return meta
