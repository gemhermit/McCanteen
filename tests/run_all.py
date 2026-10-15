#!/usr/bin/env python3
"""测试总入口：依次运行全部测试文件并汇总。"""
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TEST_FILES = [
    "test_models.py",
    "test_timeslots.py",
    "test_decide.py",
    "test_expiring.py",
    "test_life.py",
    "test_cardgen.py",
]


def main() -> int:
    total_pass = total_fail = 0
    failed = []
    for name in TEST_FILES:
        print("=" * 56)
        print(f"运行 {name}")
        print("=" * 56)
        proc = subprocess.run([sys.executable, str(TESTS_DIR / name)], capture_output=False)
        # 从输出无法直接拿计数，这里以退出码为准
        if proc.returncode != 0:
            failed.append(name)
    print("=" * 56)
    if failed:
        print(f"失败：{', '.join(failed)}")
        return 1
    print("全部测试文件通过 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
