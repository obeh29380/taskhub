import copy
import json
import os

from git import Repo

DIR = os.path.join('/app')

async def git_clone(url: str, branch: str = "main"):
    repo = Repo.clone_from(url, DIR)

async def git_pull(dir: str):
    repo = Repo(DIR)
    repo = Repo.pull()

def chown_recursive(path: str):
    uid, gid = os.getuid(), os.getgid()
    os.chown(path, uid, gid)
    print('chown', path, uid, gid)
    for root, dirs, files in os.walk(path):
        for d in dirs:
            os.chown(os.path.join(root, d), uid, gid)
        for f in files:
            os.chown(os.path.join(root, f), uid, gid)

def update_repo(url: str, dir: str, options: list = []):
    if os.path.exists(os.path.join(dir, ".git")):
        # 別でcloneした場合権限不足でエラーになる場合があるので変えておく
        chown_recursive(dir)
        repo = Repo(dir)
        repo.remotes.origin.pull()
    else:
        repo = Repo.clone_from(url, dir, multi_options=options)

def get_problems(dir: str) -> list:
    d = []
    problems_dir = os.path.join(dir, "problems")
    if not os.path.exists(problems_dir):
        print('Problems directory not found. Creating...', problems_dir)
        os.mkdir(problems_dir)
        return d
    with os.scandir(problems_dir) as it:
        for entry in it:
            if not entry.is_dir():
                continue

            with open(os.path.join(entry.path, "meta.json"), "r", encoding="utf-8") as f:
                meta_json = json.load(f)
            _d = copy.deepcopy(meta_json)
            _d['id'] = entry.name
            with open(os.path.join(entry.path, "problem.txt"), "r", encoding="utf-8") as f:
                _d['detail'] = f.read()
            
            _d['tests'] = [os.path.join(entry.path, "tests", p) for p in meta_json.get("tests", [])]
            d.append(_d)
    return d