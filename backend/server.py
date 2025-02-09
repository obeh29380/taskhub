import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
import docker
import queue
import asyncio
import copy

# from utils.git import update_repo
from utils.git import update_repo, get_problems

app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
client = docker.from_env()
app_root = os.path.dirname(__file__)
PROBLEMBS_DIR = os.path.join('/app', 'taskhub-problems')
problems = None

# app.mount("/static", StaticFiles(directory=os.path.join(app_root, "static"), html=True), name="static")

@app.on_event("startup")
async def startup_event():
    global problems
    await update_repo(os.environ["REPO_URL"], PROBLEMBS_DIR)
    problems = get_problems(PROBLEMBS_DIR)
    for _ in range(MAX_CONCURRENT_CONTAINERS):
        asyncio.create_task(worker_task())

# index.html を / で返す
@app.get("/", response_class=HTMLResponse)
async def read_root():
    file_name = "index.html"
    with open(os.path.join(app_root, "static", file_name), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

MAX_CONCURRENT_CONTAINERS = 100
queue = asyncio.Queue()
semaphore = asyncio.Semaphore(MAX_CONCURRENT_CONTAINERS)

def worker():
    while True:
        item = q.get()
        q.task_done()

def mock_db_assignment(uuid: str = None):

    # d = {
    #     "20250201-0001": {"name": "python-learning-01", "image": "python:3.11", "exec_command": ["python3", "-c", "{code}"],
    #                       "detail": "指定した数値の階乗を計算するプログラム`factorial`を作成してください。", "test_ids": ["1", "2"]},
    #     "20250201-0002": {"name": "python-learning-02", "image": "python:3.11", "exec_command": ["python3", "-c", "{code}"],
    #                       "detail": "テストなしのやつ", "test_ids": []},
    #     "20250201-0011": {"name": "rust-learning-01", "image": "rust:latest", "exec_command": ["sh", "-c", "echo '{code}' > /tmp/main.rs && rustc -o /tmp/main /tmp/main.rs && /tmp/main"]},
    # }
    if uuid is None:
        return problems
    else:
        return problems[uuid]

def mock_db_test(test_paths: list):

    # d = {
    #     "1": {"code": "assert factorial(1) == 1\nassert factorial(2) == 4\nassert factorial(3) == 9\nassert factorial(4) == 16\n"},
    #     "2": {"code": "assert factorial(0) == 1"},
    # }
    # res = dict()
    # for _id in _ids:
    #     res[_id] = d[_id]
    res = list()
    for p in test_paths:
        with open(p, "r", encoding="utf-8") as f:
            res.append({"code": f.read()})
    return res

class CodeRequest(BaseModel):
    code: str
    assignment_id: str

async def run_container(image: str, command: list):
    async with semaphore:
        mode = docker.types.ServiceMode('replicated-job', replicas=1, concurrency=1)
        rp = docker.types.RestartPolicy('none')
        # constraints = ['node.role == worker']
        constraints = []
        service = client.services.create(image, command, constraints=constraints,
                                         mode=mode, restart_policy=rp
                                        )

        tasks = service.tasks()
        while len(tasks) == 0:
            tasks = service.tasks()
        finished_tasks = []
        while True:
            tasks = list(service.tasks())
            all_finished = True
            for task in tasks:
                state = task["Status"]["State"]
                if state not in ["complete", "failed", "shutdown"]:
                    all_finished = False
                    break
                task_cp = copy.deepcopy(task["Status"]["ContainerStatus"])
                finished_tasks.append(task_cp)
            else:
                if all_finished:
                    break

            await asyncio.sleep(0.1)

        logs, attrs = b"".join(service.logs(stdout=True, stderr=True)), finished_tasks[0]
        service.remove()
        return logs, attrs

@app.get("/assignment")
async def get_assignment_list():

    assignments = mock_db_assignment()
    return assignments

@app.get("/assignment/{assignment_id}")
async def run_code(assignment_id: str):

    assignment = mock_db_assignment(assignment_id)
    return assignment

async def run_and_get_result(request: CodeRequest):

    assignment = mock_db_assignment(request.assignment_id)
    res = []
    # テストコードがあればテストコード単位に実行
    # テスコトードごとに、直列に実行される（いずれ並列にしたい）
    try:
        if len(assignment['tests']) > 0:
            test_codes = mock_db_test(assignment['tests'])
            for test_code in test_codes:
                _code = request.code
                _code += "\n"
                _code += test_code["code"]
                command = [arg.format(code=_code) for arg in assignment["exec_command"]]
                logs, attrs = await run_container(assignment["image"], command)
                if attrs["ExitCode"] == 0:
                    stdout = logs.decode("utf-8")
                    stderr = ""
                else:
                    stdout = ""
                    stderr = logs.decode("utf-8")
                res.append({
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": attrs["ExitCode"],
                    "execution_time": 0,
                    "memory_usage_kb": "N/A"
                })
        else:
            _code = request.code
            command = [arg.format(code=_code) for arg in assignment["exec_command"]]
            logs, attrs = await run_container(assignment["image"], command)
            if attrs["ExitCode"] == 0:
                stdout = logs.decode("utf-8")
                stderr = ""
            else:
                stdout = ""
                stderr = logs.decode("utf-8")
            res.append({
                "stdout": stdout,
                "stderr": stderr,
                "returncode": attrs["ExitCode"],
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
