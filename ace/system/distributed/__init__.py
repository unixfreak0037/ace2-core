# vim: ts=4:sw=4:et:cc=120
#

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import APIKeyHeader


async def verify_api_key(x_api_key: str = Depends(APIKeyHeader(name="X-API-Key"))):
    if not await app.state.system.verify_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")


app = FastAPI(dependencies=[Depends(verify_api_key)])

# importing these modules is what ends up loading the routes
import ace.system.distributed.alerting
import ace.system.distributed.analysis_module
import ace.system.distributed.analysis_request
import ace.system.distributed.config
import ace.system.distributed.storage
import ace.system.distributed.work_queue
