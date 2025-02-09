from concurrent.futures import ProcessPoolExecutor
import requests

def test_py_0():
    code = """
import random
import time
a = random.randint(1, 10000)
b = random.randint(1, 5)
start_time = time.time()
print("Start time:", start_time, "a:", a, "b:", b)
for i in range(5):
    a += i
    time.sleep(b)
end_time = time.time()
print("End time:", end_time, "a:", a, "b:", b)
"""

    response = requests.post("http://localhost/run",
                             json={"assignment_id": "20250201-0002", "code": code},
                             headers={"Content-Type": "application/json"})
    print(response.text)

def test_py_1():
    code = """
import time
def factorial(n):
  time.sleep(1)
  if n == 0:
    return 1
  else:
    return n*n
"""

    response = requests.post("http://localhost/run",
                             json={"assignment_id": "20250201-0001", "code": code},
                             headers={"Content-Type": "application/json"})
    print(response.json()['stdout'])

def test_rust_0():
    code = """
use std::thread;
use std::time::Duration;

fn main() {
    println!("Starting...");
    thread::sleep(Duration::from_secs(5));
    println!("Done waiting!");
}
"""

    response = requests.post("http://localhost/run",
                             json={"assignment_id": "20250201-0011", "code": code},
                             headers={"Content-Type": "application/json"})
    print(response.json()['stdout'])

if __name__ == "__main__":
    test_py_0()
    # count = 1
    # with ProcessPoolExecutor(max_workers=count) as executor:
    #     for i in range(count):
    #         executor.submit(test_py_0)
            # executor.submit(test_py_1)
            # executor.submit(test_rust_0)
