# vim: ts=4:sw=4:et:cc=120
#

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import APIKeyHeader

TAG_ALERTS = "alerts"
TAG_AUTH = "authentication"
TAG_ANALYSIS_MODULE = "analysis modules"
TAG_ANALYSIS_REQUEST = "analysis requests"
TAG_CONFIG = "configuration"
TAG_STORAGE = "storage"
TAG_WORK_QUEUE = "work queue"

tags_metadata = [
    {
        "name": TAG_ALERTS,
        "description": "Operations related to receiving alerts from the core.",
    },
    {
        "name": TAG_AUTH,
        "description": "API key management routines.",
    },
    {
        "name": TAG_ANALYSIS_MODULE,
        "description": "Operations related to analysis modules.",
    },
    {
        "name": TAG_ANALYSIS_REQUEST,
        "description": "Operations related to analysis requests, such as requesting analysis work, posting new analysis requests, or submitting analysis results.",
    },
    {
        "name": TAG_CONFIG,
        "description": "Get and set configuration settings.",
    },
    {
        "name": TAG_STORAGE,
        "description": "Store and retrieve arbitrary files.",
    },
    {
        "name": TAG_WORK_QUEUE,
        "description": "Operations related to work queues.",
    },
]


async def verify_api_key(x_api_key: str = Depends(APIKeyHeader(name="X-API-Key"))):
    if not await app.state.system.verify_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")


async def verify_admin_api_key(x_api_key: str = Depends(APIKeyHeader(name="X-API-Key"))):
    if not await app.state.system.verify_api_key(x_api_key, is_admin=True):
        raise HTTPException(status_code=403, detail="Invalid API key")


app = FastAPI(
    title="ACE2 Remote API", version="1.0.0", openapi_tags=tags_metadata, dependencies=[Depends(verify_api_key)]
)

# importing these modules is what ends up loading the routes
import ace.system.distributed.alerting
import ace.system.distributed.auth
import ace.system.distributed.analysis_module
import ace.system.distributed.analysis_request
import ace.system.distributed.config
import ace.system.distributed.storage
import ace.system.distributed.work_queue
