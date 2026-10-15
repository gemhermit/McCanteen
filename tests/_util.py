"""零依赖测试基座：每个测试文件独立进程运行，run_all.py 汇总。"""
from __future__ import annotations

import sys

PASS = 0
FAIL = 0


def section(name: str) -> None:
    print(f"\n[{name}]")


def check(cond, msg: str) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {msg}")
    else:
        FAIL += 1
        print(f"  FAIL {msg}")


def summary() -> int:
    print(f"\n通过 {PASS} / 失败 {FAIL}")
    return 0 if FAIL == 0 else 1


def finish() -> None:
    sys.exit(summary())
