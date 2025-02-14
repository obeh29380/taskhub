from concurrent.futures import ProcessPoolExecutor
import requests

def test_py_0(url, problem_id):
    code = """
import random
import time
a = random.randint(1, 10000)
b = random.randint(1, 5)
for i in range(5):
    a += i
    time.sleep(b)
print('done')
"""

    response = requests.post(f"{url}/run",
                             json={"problem_id": problem_id, "code": code},
                             headers={"Content-Type": "application/json"})
    res = response.json()
    assert res[0]['stdout'] == 'done\n'
    assert res[0]['stderr'] == ''
    assert res[0]['task']['Status']['ContainerStatus']['ExitCode'] == 0

def test_py_1(url, problem_id):
    code = """
def multiple(a, n):
  return a ** n
"""

    response = requests.post(f"{url}/run",
                             json={"problem_id": problem_id, "code": code},
                             headers={"Content-Type": "application/json"})
    res = response.json()
    assert res[0]['stdout'] == ''
    assert res[0]['stderr'] == ''
    assert res[0]['task']['Status']['ContainerStatus']['ExitCode'] == 0

def test_rust_0(url, problem_id):
    code = """
use std::thread;
use std::time::Duration;

fn main() {
    thread::sleep(Duration::from_secs(5));
    println!("done");
}
"""

    response = requests.post(f"{url}/run",
                             json={"problem_id": problem_id, "code": code},
                             headers={"Content-Type": "application/json"})
    res = response.json()
    assert res[0]['stdout'] == 'done\n'
    assert res[0]['stderr'] == ''
    assert res[0]['task']['Status']['ContainerStatus']['ExitCode'] == 0

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    url = f"http://localhost:{args.port}"
    # test run
    test_py_0(url, '20240209-000001')
    # count = 1
    if args.count == 0:
        exit(0)
    with ProcessPoolExecutor(max_workers=args.count) as executor:
        for i in range(args.count):
            executor.submit(test_py_0, url=url, problem_id='20240209-000001')
            executor.submit(test_py_1, url=url, problem_id='20240209-000002')
            executor.submit(test_rust_0, url=url, problem_id='20240209-000003')
