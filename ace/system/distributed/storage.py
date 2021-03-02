# vim: ts=4:sw=4:et:cc=120

import io

from typing import Optional, Union

from ace.data_model import ContentMetadata, ErrorModel
from ace.system.distributed import app
from ace.system.storage import store_content, get_content_meta, get_content_stream

from fastapi import UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse


@app.post(
    "/storage",
    responses={
        200: {"model": ContentMetadata},
        400: {"model": ErrorModel},
    },
)
def api_store_content(
    file: UploadFile = File(...),
    name: str = Form(...),
    expiration_date: Optional[str] = Form(None),
    custom: Optional[str] = Form(None),
):

    if expiration_date:
        expiration_date = datetime.fromisoformat(expiration_date)

    meta = ContentMetadata(name=name, expiration_date=expiration_date, custom=custom)

    sha256 = store_content(file.file._file, meta)
    return get_content_meta(sha256)


@app.get("/storage/{sha256}")
async def api_get_content(sha256: str = Query(...)):
    meta = get_content_meta(sha256)
    if meta is None:
        raise HTTPException(status_code=404, details=f"Content with sha256 {sha256} not found.")

    def _reader(sha256: str):
        with get_content_stream(sha256) as fp:
            while True:
                chunk = fp.read(io.DEFAULT_BUFFER_SIZE)
                if chunk == b"":
                    break

                yield chunk

    # see https://www.starlette.io/responses/#streamingresponse
    return StreamingResponse(_reader(sha256), media_type="application/octet-stream")


@app.get(
    "/storage/meta/{sha256}",
    responses={
        200: {"model": ContentMetadata},
    },
)
def api_get_content_meta(sha256: str = Query(...)) -> Union[ContentMetadata, None]:
    meta = get_content_meta(sha256)
    if meta is None:
        raise HTTPException(status_code=404, details=f"Content with sha256 {sha256} not found.")

    return meta
