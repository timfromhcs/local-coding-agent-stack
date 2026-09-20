"""
Standardized Coding Benchmark Suite for RSI Loop:
Contains 20 canonical coding tasks with unit tests measuring pass@1,
latency, and token throughput against local inference engines.
"""

import sys
import time
import json
import re
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

@dataclass
class BenchmarkTask:
    task_id: str
    name: str
    category: str
    prompt: str
    function_name: str
    test_cases: List[Dict[str, Any]]  # [{"args": [...], "expected": ...}]

BENCHMARK_TASKS: List[BenchmarkTask] = [
    BenchmarkTask(
        task_id="algo-01",
        name="Fibonacci",
        category="algorithm",
        prompt="Write a Python function `fibonacci(n: int) -> int` that returns the n-th Fibonacci number where fibonacci(0) = 0 and fibonacci(1) = 1. Return ONLY the code block.",
        function_name="fibonacci",
        test_cases=[
            {"args": [0], "expected": 0},
            {"args": [1], "expected": 1},
            {"args": [6], "expected": 8},
            {"args": [10], "expected": 55},
        ]
    ),
    BenchmarkTask(
        task_id="algo-02",
        name="Palindrome Check",
        category="algorithm",
        prompt="Write a Python function `is_palindrome(s: str) -> bool` that checks if an alphanumeric string is a palindrome, ignoring casing and non-alphanumeric characters. Return ONLY the code block.",
        function_name="is_palindrome",
        test_cases=[
            {"args": ["A man, a plan, a canal: Panama"], "expected": True},
            {"args": ["race a car"], "expected": False},
            {"args": [" "], "expected": True},
            {"args": ["Was it a car or a cat I saw?"], "expected": True},
        ]
    ),
    BenchmarkTask(
        task_id="algo-03",
        name="Two Sum",
        category="data_structures",
        prompt="Write a Python function `two_sum(nums: list, target: int) -> list` that returns indices of the two numbers such that they add up to target. Return indices sorted. Return ONLY the code block.",
        function_name="two_sum",
        test_cases=[
            {"args": [[2, 7, 11, 15], 9], "expected": [0, 1]},
            {"args": [[3, 2, 4], 6], "expected": [1, 2]},
            {"args": [[3, 3], 6], "expected": [0, 1]},
        ]
    ),
    BenchmarkTask(
        task_id="algo-04",
        name="Valid Parentheses",
        category="data_structures",
        prompt="Write a Python function `valid_parentheses(s: str) -> bool` that determines if input string of '()[]{}' brackets is valid. Return ONLY the code block.",
        function_name="valid_parentheses",
        test_cases=[
            {"args": ["()"], "expected": True},
            {"args": ["()[]{}"], "expected": True},
            {"args": ["(]"], "expected": False},
            {"args": ["([)]"], "expected": False},
            {"args": ["{[]}"], "expected": True},
        ]
    ),
    BenchmarkTask(
        task_id="algo-05",
        name="Reverse Words",
        category="strings",
        prompt="Write a Python function `reverse_words(s: str) -> str` that reverses the order of words in a string, stripping excess whitespace between words. Return ONLY the code block.",
        function_name="reverse_words",
        test_cases=[
            {"args": ["the sky is blue"], "expected": "blue is sky the"},
            {"args": ["  hello world  "], "expected": "world hello"},
            {"args": ["a good   example"], "expected": "example good a"},
        ]
    ),
    BenchmarkTask(
        task_id="algo-06",
        name="Binary Search",
        category="algorithm",
        prompt="Write a Python function `binary_search(arr: list, target: int) -> int` that returns index of target in sorted list arr, or -1 if not found. Return ONLY the code block.",
        function_name="binary_search",
        test_cases=[
            {"args": [[-1, 0, 3, 5, 9, 12], 9], "expected": 4},
            {"args": [[-1, 0, 3, 5, 9, 12], 2], "expected": -1},
            {"args": [[5], 5], "expected": 0},
            {"args": [[], 1], "expected": -1},
        ]
    ),
    BenchmarkTask(
        task_id="algo-07",
        name="Merge Intervals",
        category="algorithm",
        prompt="Write a Python function `merge_intervals(intervals: list) -> list` that merges all overlapping intervals and returns non-overlapping intervals sorted by start time. Return ONLY the code block.",
        function_name="merge_intervals",
        test_cases=[
            {"args": [[[1, 3], [2, 6], [8, 10], [15, 18]]], "expected": [[1, 6], [8, 10], [15, 18]]},
            {"args": [[[1, 4], [4, 5]]], "expected": [[1, 5]]},
        ]
    ),
    BenchmarkTask(
        task_id="algo-08",
        name="Max Subarray Sum",
        category="algorithm",
        prompt="Write a Python function `max_subarray_sum(nums: list) -> int` that finds contiguous subarray with largest sum and returns its sum. Return ONLY the code block.",
        function_name="max_subarray_sum",
        test_cases=[
            {"args": [[-2, 1, -3, 4, -1, 2, 1, -5, 4]], "expected": 6},
            {"args": [[1]], "expected": 1},
            {"args": [[5, 4, -1, 7, 8]], "expected": 23},
        ]
    ),
    BenchmarkTask(
        task_id="algo-09",
        name="Longest Common Prefix",
        category="strings",
        prompt="Write a Python function `longest_common_prefix(strs: list) -> str` that finds the longest common prefix among a list of strings, or empty string if none. Return ONLY the code block.",
        function_name="longest_common_prefix",
        test_cases=[
            {"args": [["flower", "flow", "flight"]], "expected": "fl"},
            {"args": [["dog", "racecar", "car"]], "expected": ""},
            {"args": [["interspecies", "interstellar", "interstate"]], "expected": "inters"},
        ]
    ),
    BenchmarkTask(
        task_id="algo-10",
        name="Find Duplicates",
        category="data_structures",
        prompt="Write a Python function `find_duplicates(nums: list) -> list` that returns all integers that appear more than once, sorted in ascending order. Return ONLY the code block.",
        function_name="find_duplicates",
        test_cases=[
            {"args": [[4, 3, 2, 7, 8, 2, 3, 1]], "expected": [2, 3]},
            {"args": [[1, 1, 2]], "expected": [1]},
            {"args": [[1]], "expected": []},
        ]
    ),
    BenchmarkTask(
        task_id="algo-11",
        name="Group Anagrams",
        category="strings",
        prompt="Write a Python function `group_anagrams(words: list) -> list` that groups anagrams together. Each group should be sorted, and the outer list sorted by first element. Return ONLY the code block.",
        function_name="group_anagrams",
        test_cases=[
            {"args": [["eat", "tea", "tan", "ate", "nat", "bat"]], "expected": [["ate", "eat", "tea"], ["bat"], ["nat", "tan"]]},
            {"args": [[""]], "expected": [[""]]},
        ]
    ),
    BenchmarkTask(
        task_id="algo-12",
        name="Climb Stairs",
        category="algorithm",
        prompt="Write a Python function `climb_stairs(n: int) -> int` that returns distinct ways to climb n stairs taking 1 or 2 steps each time. Return ONLY the code block.",
        function_name="climb_stairs",
        test_cases=[
            {"args": [2], "expected": 2},
            {"args": [3], "expected": 3},
            {"args": [5], "expected": 8},
        ]
    ),
    BenchmarkTask(
        task_id="algo-13",
        name="Flatten Nested List",
        category="recursion",
        prompt="Write a Python function `flatten_nested_list(nested: list) -> list` that deeply flattens an arbitrarily nested list of integers. Return ONLY the code block.",
        function_name="flatten_nested_list",
        test_cases=[
            {"args": [[[1, [2]], [3, [4, [5]]]]], "expected": [1, 2, 3, 4, 5]},
            {"args": [[[], [1, []], 2]], "expected": [1, 2]},
            {"args": [[]], "expected": []},
        ]
    ),
    BenchmarkTask(
        task_id="algo-14",
        name="Coin Change",
        category="dynamic_programming",
        prompt="Write a Python function `coin_change(coins: list, amount: int) -> int` that computes fewest coins to make up that amount, or -1 if impossible. Return ONLY the code block.",
        function_name="coin_change",
        test_cases=[
            {"args": [[1, 2, 5], 11], "expected": 3},
            {"args": [[2], 3], "expected": -1},
            {"args": [[1], 0], "expected": 0},
        ]
    ),
    BenchmarkTask(
        task_id="algo-15",
        name="Count Islands",
        category="graphs",
        prompt="Write a Python function `count_islands(grid: list) -> int` that counts islands in a 2D binary grid (1=land, 0=water) connected horizontally or vertically. Return ONLY the code block.",
        function_name="count_islands",
        test_cases=[
            {"args": [[[1, 1, 0], [1, 1, 0], [0, 0, 1]]], "expected": 2},
            {"args": [[[1, 0], [0, 1]]], "expected": 2},
            {"args": [[[0, 0], [0, 0]]], "expected": 0},
        ]
    ),
    BenchmarkTask(
        task_id="algo-16",
        name="Top K Frequent",
        category="data_structures",
        prompt="Write a Python function `top_k_frequent(nums: list, k: int) -> list` that returns the k most frequent elements sorted in descending order of frequency. Return ONLY the code block.",
        function_name="top_k_frequent",
        test_cases=[
            {"args": [[1, 1, 1, 2, 2, 3], 2], "expected": [1, 2]},
            {"args": [[1], 1], "expected": [1]},
        ]
    ),
    BenchmarkTask(
        task_id="algo-17",
        name="Evaluate RPN",
        category="stacks",
        prompt="Write a Python function `evaluate_rpn(tokens: list) -> int` that evaluates arithmetic expressions in Reverse Polish Notation ('+', '-', '*', '/'). Integer division truncates towards zero. Return ONLY the code block.",
        function_name="evaluate_rpn",
        test_cases=[
            {"args": [["2", "1", "+", "3", "*"]], "expected": 9},
            {"args": [["4", "13", "5", "/", "+"]], "expected": 6},
            {"args": [["10", "6", "9", "3", "+", "-11", "*", "/", "*", "17", "+", "5", "+"]], "expected": 22},
        ]
    ),
    BenchmarkTask(
        task_id="algo-18",
        name="Word Frequency",
        category="strings",
        prompt="Write a Python function `word_frequency(text: str) -> dict` that counts occurrences of words (lowercase, whitespace separated, punctuation removed). Return ONLY the code block.",
        function_name="word_frequency",
        test_cases=[
            {"args": ["apple banana apple"], "expected": {"apple": 2, "banana": 1}},
            {"args": ["Hello, hello world!"], "expected": {"hello": 2, "world": 1}},
        ]
    ),
    BenchmarkTask(
        task_id="algo-19",
        name="Compress String",
        category="strings",
        prompt="Write a Python function `compress_string(s: str) -> str` using counts of repeated characters (e.g. 'aabcccccaaa' -> 'a2b1c5a3'). Return original string if compressed length not smaller. Return ONLY the code block.",
        function_name="compress_string",
        test_cases=[
            {"args": ["aabcccccaaa"], "expected": "a2b1c5a3"},
            {"args": ["abcdef"], "expected": "abcdef"},
            {"args": [""], "expected": ""},
        ]
    ),
    BenchmarkTask(
        task_id="algo-20",
        name="Matrix Transpose",
        category="math",
        prompt="Write a Python function `matrix_transpose(matrix: list) -> list` that returns the transpose of a given 2D matrix. Return ONLY the code block.",
        function_name="matrix_transpose",
        test_cases=[
            {"args": [[[1, 2, 3], [4, 5, 6]]], "expected": [[1, 4], [2, 5], [3, 6]]},
            {"args": [[[1, 2], [3, 4]]], "expected": [[1, 3], [2, 4]]},
            {"args": [[]], "expected": []},
        ]
    ),
]

def extract_code_block(text: str) -> str:
    """Extract code from markdown block or raw text."""
    match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

def execute_code_safely(code: str, function_name: str, args: list) -> Tuple[bool, Any]:
    """Execute extracted code in a restricted scope."""
    scope = {}
    try:
        exec(code, scope)
        if function_name not in scope:
            return False, f"Function '{function_name}' not defined in generated code."
        fn = scope[function_name]
        result = fn(*args)
        return True, result
    except Exception as e:
        return False, str(e)

def run_task(endpoint_url: str, task: BenchmarkTask, timeout_sec: int = 30) -> Dict[str, Any]:
    """Send single benchmark task to OpenAI-compatible /v1/chat/completions endpoint."""
    payload = {
        "model": "local-model",
        "messages": [
            {"role": "system", "content": "You are an expert Python software engineer. Implement the requested function correctly with no explanation, inside a ```python ``` block."},
            {"role": "user", "content": task.prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 1024
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{endpoint_url.rstrip('/')}/v1/chat/completions",
        data=req_data,
        headers={"Content-Type": "application/json"}
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed_sec = time.perf_counter() - t0
    except Exception as e:
        return {
            "task_id": task.task_id,
            "name": task.name,
            "passed": False,
            "error": f"Request failed: {e}",
            "latency_ms": (time.perf_counter() - t0) * 1000,
            "tokens": 0,
            "tps": 0.0
        }

    raw_output = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = data.get("usage", {})
    completion_tokens = usage.get("completion_tokens", len(raw_output.split()))
    tps = completion_tokens / max(elapsed_sec, 0.001)

    code = extract_code_block(raw_output)

    # Run unit tests
    all_passed = True
    test_failures = []

    for idx, tc in enumerate(task.test_cases):
        args = tc["args"]
        expected = tc["expected"]
        success, result = execute_code_safely(code, task.function_name, args)
        if not success:
            all_passed = False
            test_failures.append(f"TC#{idx} Error: {result}")
        elif result != expected:
            all_passed = False
            test_failures.append(f"TC#{idx} Failed: expected {expected!r}, got {result!r}")

    return {
        "task_id": task.task_id,
        "name": task.name,
        "category": task.category,
        "passed": all_passed,
        "test_failures": test_failures,
        "latency_ms": elapsed_sec * 1000,
        "tokens": completion_tokens,
        "tps": tps,
        "code_snippet": code[:100] + "..." if len(code) > 100 else code
    }

def run_benchmark_suite(endpoint_url: str = "http://127.0.0.1:8080", max_tasks: Optional[int] = None) -> Dict[str, Any]:
    """Run benchmark suite against the target endpoint and compile aggregate report."""
    tasks = BENCHMARK_TASKS[:max_tasks] if max_tasks else BENCHMARK_TASKS
    results = []

    t_start = time.perf_counter()
    for task in tasks:
        res = run_task(endpoint_url, task)
        results.append(res)

    total_duration = time.perf_counter() - t_start
    n_passed = sum(1 for r in results if r["passed"])
    n_total = len(results)
    pass_rate = (n_passed / n_total) if n_total > 0 else 0.0

    latencies = [r["latency_ms"] for r in results]
    mean_latency = sum(latencies) / len(latencies) if latencies else 0.0
    total_tokens = sum(r["tokens"] for r in results)
    avg_tps = total_tokens / max(total_duration, 0.001)

    return {
        "timestamp": time.time(),
        "endpoint": endpoint_url,
        "tasks_run": n_total,
        "tasks_passed": n_passed,
        "pass_rate": round(pass_rate, 4),
        "mean_latency_ms": round(mean_latency, 2),
        "total_duration_s": round(total_duration, 2),
        "avg_tokens_per_sec": round(avg_tps, 2),
        "task_results": results
    }

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    print(f"Running RSI Benchmark Suite against {url} ({limit or len(BENCHMARK_TASKS)} tasks)...")
    report = run_benchmark_suite(url, max_tasks=limit)
    print(f"Result: {report['tasks_passed']}/{report['tasks_run']} passed ({report['pass_rate']*100:.1f}%)")
    print(f"Mean Latency: {report['mean_latency_ms']} ms | Throughput: {report['avg_tokens_per_sec']} t/s")
    for r in report["task_results"]:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['task_id']} {r['name']} ({r['latency_ms']:.0f}ms)")
