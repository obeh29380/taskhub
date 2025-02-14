import os

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
import docker
import queue
import asyncio
import copy
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from utils.git import update_repo, get_problems

app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
client = docker.from_env()
app_root = os.path.dirname(__file__)
PROBLEMBS_DIR = os.path.join('/app', 'taskhub-problems')
problems = None
problems_list = None

# app.mount("/static", StaticFiles(directory=os.path.join(app_root, "static"), html=True), name="static")

def update_problems():
    global problems
    global problems_list
    if os.getenv("REPO_URL") is not None and os.getenv("REPO_URL") != "":
        update_repo(os.environ["REPO_URL"], PROBLEMBS_DIR)
    print("Load problems", problems_list)
    problems_list = get_problems(PROBLEMBS_DIR)
    problems = {p["id"]: p for p in problems_list}

@app.exception_handler(RequestValidationError)
async def handler(request:Request, exc:RequestValidationError):
    print(exc)
    return JSONResponse(content={}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

@app.on_event("startup")
def startup_event():
    update_problems()
    for _ in range(MAX_CONCURRENT_CONTAINERS):
        asyncio.create_task(worker_task())

@app.get("/", response_class=HTMLResponse)
async def read_root():
    file_name = "index.html"
    with open(os.path.join(app_root, "static", file_name), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

MAX_CONCURRENT_CONTAINERS = 1000
queue = asyncio.Queue()
semaphore = asyncio.Semaphore(MAX_CONCURRENT_CONTAINERS)

def worker():
    while True:
        item = q.get()
        q.task_done()

def read_test_code(test_paths: list):

    res = list()
    for p in test_paths:
        with open(p, "r", encoding="utf-8") as f:
            res.append({"code": f.read()})
    return res

def get_swarm_worker_count() -> int:
    """workerノード取得"""
    try:
        nodes = client.nodes.list()
        worker_count = sum(1 for node in nodes if node.attrs["Spec"]["Role"] == "worker")
        return worker_count
    except Exception as e:
        print("Error retrieving nodes:", e)
        return 0


class CodeRequest(BaseModel):
    code: str
    problem_id: str

async def run_container(image: str, command: list):
    async with semaphore:
        mode = docker.types.ServiceMode('replicated-job', replicas=1, concurrency=1)
        rp = docker.types.RestartPolicy('none')
        constraints = []
        if get_swarm_worker_count() > 0:
            constraints.append('node.role == worker')
        one_cpu = 1000000000
        mem_1g = 1024*1024*1024
        resources = docker.types.Resources(cpu_limit=int(float(os.getenv("DOCKER_SERVICE_CPU_LIMIT", "0.5"))*one_cpu),
                                           mem_limit=int(float(os.getenv("DOCKER_SERVICE_MEM_LIMIT", "1"))*mem_1g))
        service = client.services.create(image, command, constraints=constraints,
                                         mode=mode, restart_policy=rp, resources=resources
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
                task_cp = copy.deepcopy(task)
                # ["Status"]["ContainerStatus"]
                finished_tasks.append(task_cp)
            else:
                if all_finished:
                    break

            await asyncio.sleep(0.1)

        logs, task = b"".join(service.logs(stdout=True, stderr=True)), finished_tasks[0]
        service.remove()
        return logs, task

@app.get("/problem")
async def get_problem_list():
    global problems_list
    return problems_list

@app.get("/problem/{problem_id}")
async def run_code(problem_id: str):

    return problems[problem_id]

async def run_and_get_result(request: CodeRequest):

    problem = problems[request.problem_id]
    res = []
    # テストコードがあればテストコード単位に実行
    # テスコトードごとに、直列に実行される（いずれ並列にしたい）
    try:
        if len(problem['tests']) > 0:
            test_codes = read_test_code(problem['tests'])
            for test_code in test_codes:
                _code = request.code
                _code += "\n"
                _code += test_code["code"]
                command = [arg.format(code=_code) for arg in problem["exec_command"]]
                logs, task = await run_container(problem["image"], command)
                if task["Status"]["ContainerStatus"]["ExitCode"] == 0:
                    stdout = logs.decode("utf-8")
                    stderr = ""
                else:
                    stdout = ""
                    stderr = logs.decode("utf-8")
                res.append({
                    "stdout": stdout,
                    "stderr": stderr,
                    "task": task,
                    "memory_usage_kb": "N/A"
                })
        else:
            _code = request.code
            command = [arg.format(code=_code) for arg in problem["exec_command"]]
            logs, task = await run_container(problem["image"], command)
            if task["Status"]["ContainerStatus"]["ExitCode"] == 0:
                stdout = logs.decode("utf-8")
                stderr = ""
            else:
                stdout = ""
                stderr = logs.decode("utf-8")
            res.append({
                "stdout": stdout,
                "stderr": stderr,
                "task": task,
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

def require_admin(func):
    """管理者権限があることをチェックする
    環境変数に設定した管理者用パスワードが認証ヘッダにセットされているかを確認する
    """
    async def wrapper(*args, **kwargs):
        admin_password = os.getenv("ADMIN_PASSWORD")
        if admin_password is None:
            raise HTTPException(status_code=500, detail="ADMIN_PASSWORD is not set")
        if "Authorization" not in args[0].headers:
            raise HTTPException(status_code=401, detail="Authorization header is missing")
        if args[0].headers["Authorization"] != f"Bearer {admin_password}":
            raise HTTPException(status_code=403, detail="Invalid Authorization header")
        return await func(*args, **kwargs)
    return wrapper

@app.post("/api/v1/admin/problem/update")
@require_admin
async def admin_api_update_problem():
    """Update problems from the repository
    """
    update_problems()
    return {"status": "ok"}

async def worker_task():
    while True:
        req, future = await queue.get()
        try:
            result = await run_and_get_result(req)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        queue.task_done()

# トータルで見ると、2ノードで1GBとれるのも1カウントになってしまうのでやめる
# したがって当面はswarmに任せる
# async def check_nodes():
#     while True:
#         await asyncio.sleep(60)
#         # workerノード取得
#         nodes = client.nodes.list(filters={'role': 'worker'})
#         for node in nodes:
#             mem = node.attrs["Description"]["Resources"]["MemoryBytes"]
#             cpu = node.attrs["Description"]["Resources"]["NanoCPUs"]
#             status = node.attrs["Status"]
#             if status["State"] == "ready":
#                 print(f"Node {node.id} is ready. CPU: {cpu}, MEM: {mem}, addr={status["State"]["Addr"]}", flush=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"),
                port=os.getenv("PORT", 8000))
    # for ssl
    #uvicorn.run(app, host="0.0.0.0", port=8000, ssl_keyfile="/app/certs/privkey.pem", ssl_certfile="/app/certs/fullchain.pem")