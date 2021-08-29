from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import APIKeyHeader

from ace.system.redis import RedisACESystem
from ace.system.database import DatabaseACESystem

TAG_ALERTS = "alerts"
TAG_AUTH = "authentication"
TAG_ANALYSIS_MODULE = "analysis modules"
TAG_ANALYSIS_REQUEST = "analysis requests"
TAG_ANALYSIS_TRACKING = "analysis tracking"
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
    {
        "name": TAG_ANALYSIS_TRACKING,
        "description": "Operations to acquire analysis data.",
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


class DistributedACESystem(RedisACESystem, DatabaseACESystem):
    pass


@app.on_event("startup")
async def startup_event():
    app.state.system = DistributedACESystem()
    await app.state.system.initialize()
    app.state.system.encryption_settings.load_from_env()
