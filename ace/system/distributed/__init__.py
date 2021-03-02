# vim: ts=4:sw=4:et:cc=120
#

from fastapi import FastAPI

app = FastAPI()

# importing these modules is what ends up loading the routes
import ace.system.distributed.analysis_module
import ace.system.distributed.work_queue
import ace.system.distributed.processing
import ace.system.distributed.storage
