import os
import sys

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import APIKeyHeader

from ace.constants import ACE_ADMIN_PASSWORD
from ace.crypto import EncryptionSettings
from ace.env import register_global_env, ACEOperatingEnvironment
from ace.system.default import DefaultACESystem

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


@app.on_event("startup")
async def startup_event():
    if ACE_ADMIN_PASSWORD not in os.environ:
        sys.stderr.write(f"\n\nERROR: missing {ACE_ADMIN_PASSWORD} env var\n\n")
        sys.exit(1)

    # register a default operating environment that ignores command line parameters
    env = register_global_env(ACEOperatingEnvironment([]))
    system = DefaultACESystem()
    env.set_system(system)

    app.state.system = system
    app.state.system.encryption_settings = EncryptionSettings()
    app.state.system.encryption_settings.load_from_env()
    app.state.system.encryption_settings.load_aes_key(os.environ[ACE_ADMIN_PASSWORD])
    await app.state.system.initialize()
