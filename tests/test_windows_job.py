"""Actual Windows process/port proofs; never assign the pytest process to a job."""
import ctypes
import json
import os
import socket
import subprocess
import sys
from ctypes import wintypes

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows job-object lifecycle")

GRANDCHILD = """
import json, os, socket, time
with socket.socket() as server:
    server.bind(('127.0.0.1', 0))
    server.listen()
    print(json.dumps({'pid': os.getpid(), 'port': server.getsockname()[1]}), flush=True)
    while True:
        time.sleep(.1)
"""
CHILD = """
import json, os, subprocess, sys, time
process = subprocess.Popen([sys.executable, '-c', sys.argv[1]], stdout=subprocess.PIPE, text=True)
ready = json.loads(process.stdout.readline())
print(json.dumps({**ready, 'child': os.getpid(), 'launcher': process.pid}), flush=True)
while True:
    time.sleep(.1)
"""
SUPERVISOR = """
import json, os, subprocess, sys
from shortlist.windows_job import protect_process_tree
if sys.argv[1] == 'protected':
    protect_process_tree()
    protect_process_tree()  # Retry is a no-op, not another nested job.
process = subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[3]], stdout=subprocess.PIPE, text=True)
ready = json.loads(process.stdout.readline())
print(json.dumps({**ready, 'supervisor': os.getpid(), 'child_launcher': process.pid}), flush=True)
if sys.stdin.readline().strip() == 'crash':
    os._exit(17)
"""


def kernel_api():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel.TerminateProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    return kernel


@pytest.mark.parametrize("exit_kind", ["normal", "crash", "forced", "unprotected-control"])
def test_supervisor_lifetime_owns_launcher_and_grandchild(exit_kind):
    kernel = kernel_api()
    protected = exit_kind != "unprotected-control"
    process = subprocess.Popen([sys.executable, "-c", SUPERVISOR,
                                "protected" if protected else "unprotected", CHILD, GRANDCHILD],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    handles = []
    try:
        ready = json.loads(process.stdout.readline())
        # Open handles before exit: PID reuse cannot make a different process pass.
        for key in ("supervisor", "child_launcher", "child", "launcher", "pid"):
            handle = kernel.OpenProcess(0x100001, False, ready[key])  # SYNCHRONIZE | PROCESS_TERMINATE
            assert handle, ctypes.WinError(ctypes.get_last_error())
            handles.append(handle)
        if exit_kind == "forced":
            assert kernel.TerminateProcess(handles[0], 19)
        else:
            process.stdin.write("crash\n" if exit_kind == "crash" else "normal\n")
            process.stdin.flush()
        process.wait(timeout=10)
        if protected:
            assert all(kernel.WaitForSingleObject(handle, 5000) == 0 for handle in handles)
            with socket.socket() as server:
                server.bind(("127.0.0.1", ready["port"]))
        else:
            # Reproduce the original bug: direct-parent exit leaves real work alive.
            assert kernel.WaitForSingleObject(handles[-1], 0) == 258
            with socket.socket() as server, pytest.raises(OSError):
                server.bind(("127.0.0.1", ready["port"]))
    finally:
        for handle in reversed(handles):
            if kernel.WaitForSingleObject(handle, 0) == 258:
                kernel.TerminateProcess(handle, 20)
                kernel.WaitForSingleObject(handle, 5000)
            kernel.CloseHandle(handle)
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdin.close()
        process.stdout.close()
