# vim: ts=4:sw=4:et:cc=120
# flake8: noqa

from ace.data_model import AnalysisRequestModel, AnalysisRequestQueryModel, ErrorModel
from ace.system.constants import ERROR_AMT_VERSION
from ace.system.exceptions import ACEError
from ace.system.distributed import app
from ace.system.work_queue import get_next_analysis_request

from fastapi import Response
from fastapi.responses import JSONResponse


@app.post(
    "/work_queue",
    responses={
        200: {"model": AnalysisRequestModel},
        400: {"model": ErrorModel},
    },
)
def api_get_next_analysis_request(query: AnalysisRequestQueryModel):
    try:
        result = get_next_analysis_request(
            query.owner,
            query.amt,
            timeout=query.timeout,
            version=query.version,
            extended_version=query.extended_version,
        )
    except ACEError as e:
        return JSONResponse(status_code=400, content=ErrorModel(code=e.code, details=str(e)).dict())

    if not result:
        return Response(status_code=204)

    return result.to_model()


# @app.delete("/work_queue/delete_queue/{name}")
# def delete_work_queue(name: str):
# return {"result": distributed_interface.delete_work_queue(name)}


# @app.put("/work_queue/add_queue/{name}")
# def add_work_queue(name: str):
# distributed_interface.add_work_queue(name)


# @app.post("/work_queue/get_work")
# def get_work(amt: str, timeout: float):
# return {"result": distributed_interface.get_work(amt, timeout)}


# @app.post("/work_queue/put_work")
# def put_work(amt: str, analysis_request: str):
# return {"result": distributed_interface.put_work(amt, analysis_request)}


# @app.get("/work_queue/queue_info/size/{name}")
# def get_work(name: str):
# return {"result": distributed_interface.get_queue_size(name)}


# @app.post("/work_queue/reset")
# def reset(name: str):
# distributed_interface.reset()


# class DistributedWorkQueueManagerInterfaceClient(WorkQueueManagerInterface):

# client = requests

# def delete_work_queue(self, name: str) -> bool:
# result = self.client.get(f"/work_queue/delete_queue/{name}")
# result.raise_for_status()
# return result.json()["result"]

# def add_work_queue(self, name: str):
# result = self.client.put(f"/work_queue/add_queue/{name}")
# result.raise_for_status()

# def put_work(self, amt: str, analysis_request: dict):
# result = self.client.post(f"/work_queue/put_work", data={"amt": amt, "analysis_request": analysis_request})
# result.raise_for_status()
# return result.json()["result"]

# def get_work(self, amt: str, timeout: float) -> Union[dict, None]:
# result = self.client.post(f"/work_queue/get_work", data={"amt": amt, "timeout": timeout})
# result.raise_for_status()
# return result.json()["result"]

# def get_queue_size(self, name: str) -> int:
# result = self.client.get(f"/work_queue/queue_info/size/{name}")
# result.raise_for_status()
# return result.json()["result"]
