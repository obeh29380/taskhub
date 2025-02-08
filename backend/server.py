from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import docker
import queue
import threading
import asyncio

app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
client = docker.from_env()

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_CONCURRENT_CONTAINERS = 3
queue = asyncio.Queue()
semaphore = asyncio.Semaphore(MAX_CONCURRENT_CONTAINERS)

def worker():
    while True:
        item = q.get()
        print(f'Working on {item}')
        print(f'Finished {item}')
        q.task_done()

def mock_db_assignment(uuid):

    d = {
        "20250201-0001": {"name": "python-learning-01", "image": "python:3.11", "exec_template": ["python3", "-c", "{code}"],
                          "detail": "指定した数値の階乗を計算するプログラム`factorial`を作成してください。", "test_ids": ["1", "2"]},
        "20250201-0002": {"name": "python-learning-02", "image": "python:3.11", "exec_template": ["python3", "-c", "{code}"],
                          "detail": "テストなしのやつ", "test_ids": []},
        "20250201-0011": {"name": "rust-learning-01", "image": "rust:latest", "exec_template": ["sh", "-c", "echo '{code}' > /tmp/main.rs && rustc -o /tmp/main /tmp/main.rs && /tmp/main"]},
    }
    return d[uuid]

def mock_db_test(_ids):

    d = {
        "1": {"code": "assert factorial(1) == 1\nassert factorial(2) == 4\nassert factorial(3) == 9\nassert factorial(4) == 16\n"},
        "2": {"code": "assert factorial(0) == 1"},
    }
    res = dict()
    for _id in _ids:
        res[_id] = d[_id]
    return res

class CodeRequest(BaseModel):
    code: str
    assignment_id: str

async def run_container(image: str, command: list):
    async with semaphore:
        # container = await loop.run_in_executor(None, client.containers.run,
        #     "python:3.11", ["python3", "-c", code], detach=True, remove=True, stdout=True, stderr=True
        # )

        container = client.containers.run(image, command, detach=True,
                                        )

        while container.status != "exited":
            container.reload()
            await asyncio.sleep(0.1)
        # exit_code = attrs["State"]["ExitCode"]
        logs, attrs = container.logs(), container.attrs
        container.remove()
        return logs, attrs

@app.get("/assignment/{assignment_id}")
async def run_code(assignment_id: str):

    assignment = mock_db_assignment(assignment_id)
    return assignment

async def run_and_get_result(request: CodeRequest):

    assignment = mock_db_assignment(request.assignment_id)
    res = []
    # テストコードがあればテストコード単位に実行（TODO 実行ごとに待機せず、１ケース目を実行したら優先的に後続も実行したい）
    try:
        if len(assignment.get("test_ids", [])) > 0:
            tests = mock_db_test(assignment["test_ids"])
            for test in tests.values():
                _code = request.code
                _code += "\n"
                _code += test["code"]
                command = [arg.format(code=_code) for arg in assignment["exec_template"]]
                logs, attrs = await run_container(assignment["image"], command)
                if attrs["State"]["ExitCode"] == 0:
                    stdout = logs.decode("utf-8")
                    stderr = ""
                else:
                    stdout = ""
                    stderr = logs.decode("utf-8")
                res.append({
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": attrs["State"]["ExitCode"],
                    "execution_time": 0,
                    "memory_usage_kb": "N/A"
                })
        else:
            _code = request.code
            command = [arg.format(code=_code) for arg in assignment["exec_template"]]
            logs, attrs = await run_container(assignment["image"], command)

            if attrs["State"]["ExitCode"] == 0:
                stdout = logs.decode("utf-8")
                stderr = ""
            else:
                stdout = ""
                stderr = logs.decode("utf-8")
            res.append({
                "stdout": stdout,
                "stderr": stderr,
                "returncode": attrs["State"]["ExitCode"],
                "execution_time": 0,
                "memory_usage_kb": "N/A"
            })
    except docker.errors.ContainerError as e:
        return {
            "stdout": e.stdout.decode("utf-8") if e.stdout else "",
            "stderr": e.stderr.decode("utf-8") if e.stderr else "",
            "returncode": e.exit_status,
            "execution_time": 0,
            "memory_usage_kb": "N/A"
        }
    # logs = await run_container(assignment["image"], command)
    return res


@app.post("/run")
async def run_code(request: CodeRequest):

    future = asyncio.Future()
    await queue.put((request, future))
    return await future
    

async def worker_task():
    while True:
        req, future = await queue.get()
        try:
            result = await run_and_get_result(req)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        queue.task_done()

# ワーカープロセスを起動（FastAPI 起動時に実行）
@app.on_event("startup")
async def startup_event():
    for _ in range(MAX_CONCURRENT_CONTAINERS):
        asyncio.create_task(worker_task())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
