"""Small, auditable process limits for the built-in pilot worker.

This is a resource governor, not a security sandbox.  It does not prevent a
child from accessing the network or paths outside its working directory.
"""
from __future__ import annotations

import math
import os
import platform
try:
    import resource
except ImportError:  # Windows
    resource = None
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from .core import DiscoveryError

try:
    import ctypes
    from ctypes import wintypes
except ImportError:  # pragma: no cover
    ctypes = None
    wintypes = None


_LIMITS = ("seconds", "memory_mb", "disk_mb", "cpu_seconds")


def _validate_limits(limits):
    if not isinstance(limits, dict) or any(k not in _LIMITS for k in limits):
        raise DiscoveryError("Unknown process limit")
    result = {k: limits.get(k) for k in _LIMITS}
    for key, value in result.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DiscoveryError("Invalid process limit: " + key)
        if not math.isfinite(value) or value <= 0:
            raise DiscoveryError("Invalid process limit: " + key)
    return result


def resources(path=None):
    path = Path(path or Path.cwd()).resolve()
    usage = shutil.disk_usage(path)
    memory = 0
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            memory = int(status.ullAvailPhys)
    elif os.path.exists("/proc/meminfo"):
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                memory = int(line.split()[1]) * 1024
                break
    if not memory:
        try:
            memory = int(os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
        except (AttributeError, ValueError, OSError):
            memory = 0
    gpu = []
    tool = shutil.which("nvidia-smi")
    if tool:
        try:
            probe = subprocess.run([tool, "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader"],
                                   capture_output=True, text=True, timeout=3)
            if probe.returncode == 0: gpu = [line for line in probe.stdout.splitlines() if line.strip()]
        except (OSError, subprocess.TimeoutExpired): pass
    return {"platform": platform.platform(), "available_memory_bytes": memory,
            "disk_free_bytes": usage.free, "cpu_count": os.cpu_count(),
            "gpu": gpu, "gpu_used": False,
            "limitations": ["stdlib governor; no network or filesystem sandbox"]}


def _tree_size(path):
    total = 0
    try:
        for item in Path(path).rglob("*"):
            if item.is_file():
                try: total += item.stat().st_size
                except OSError: pass
    except OSError: pass
    return total


def _posix_usage(pid):
    """Read Linux child CPU/RSS counters without adding psutil."""
    if os.name == "nt": return 0.0, 0
    try:
        fields = (Path("/proc") / str(pid) / "stat").read_text().split()
        ticks = os.sysconf("SC_CLK_TCK")
        cpu = (int(fields[13]) + int(fields[14])) / float(ticks)
        rss = int(fields[23]) * os.sysconf("SC_PAGE_SIZE")
        return cpu, rss
    except (OSError, IndexError, ValueError, AttributeError):
        return 0.0, 0


class _WindowsJob:
    """Job Object wrapper with explicit ctypes layouts and signatures."""
    def __init__(self, limits):
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [("ReadOperationCount", ctypes.c_ulonglong), ("WriteOperationCount", ctypes.c_ulonglong),
                        ("OtherOperationCount", ctypes.c_ulonglong), ("ReadTransferCount", ctypes.c_ulonglong),
                        ("WriteTransferCount", ctypes.c_ulonglong), ("OtherTransferCount", ctypes.c_ulonglong)]
        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]
        class Extended(ctypes.Structure):
            # JOBOBJECT_EXTENDED_LIMIT_INFORMATION order is ABI-sensitive.
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO_COUNTERS),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        self.Extended = Extended
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.AssignProcessToJobObject.restype = wintypes.BOOL
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, wintypes.INT, ctypes.c_void_p, wintypes.DWORD]
        self.api.SetInformationJobObject.restype = wintypes.BOOL
        self.api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.api.TerminateJobObject.restype = wintypes.BOOL
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle: raise OSError(ctypes.get_last_error(), "CreateJobObjectW")
        # JOB_OBJECT_LIMIT_PROCESS_TIME | JOB_OBJECT_LIMIT_JOB_MEMORY | KILL_ON_JOB_CLOSE
        info = Extended()
        # JOB_OBJECT_LIMIT_JOB_TIME (0x4), JOB_MEMORY (0x200), KILL_ON_CLOSE (0x2000)
        info.BasicLimitInformation.LimitFlags = 0x4 | 0x200 | 0x2000
        info.BasicLimitInformation.PerJobUserTimeLimit = int(limits["cpu_seconds"] * 10_000_000)
        info.JobMemoryLimit = int(limits["memory_mb"] * 1024 * 1024)
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            self.close(); raise OSError(ctypes.get_last_error(), "SetInformationJobObject")

    def assign(self, process_handle):
        if not self.api.AssignProcessToJobObject(self.handle, process_handle):
            raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject")

    def terminate(self):
        self.api.TerminateJobObject(self.handle, 1)

    def close(self):
        if getattr(self, "handle", None):
            self.api.CloseHandle(self.handle); self.handle = None


def _reader(stream, target, state, lock):
    try:
        with target.open("wb") as output:
            while True:
                block = stream.read(65536)
                if not block: break
                with lock:
                    allowance = max(0, state["cap"] - state["written"])
                    if allowance:
                        output.write(block[:allowance]); state["written"] += min(len(block), allowance)
                    if len(block) > allowance or state["written"] >= state["cap"]:
                        state["disk"] = True
                if state["disk"]:
                    break
    finally:
        stream.close()


def _windows_usage(handle):
    """Return (user+kernel CPU seconds, working-set bytes) where available."""
    if os.name != "nt": return (0.0, 0)
    try:
        class FILETIME(ctypes.Structure):
            _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]
        creation, exit_time, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME)]
        api.GetProcessTimes.restype = wintypes.BOOL
        cpu = 0.0
        if api.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time), ctypes.byref(kernel), ctypes.byref(user)):
            def val(t): return (int(t.high) << 32) | int(t.low)
            cpu = (val(kernel) + val(user)) / 10_000_000.0
        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC(); pmc.cb = ctypes.sizeof(pmc)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        memory = int(pmc.WorkingSetSize) if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb) else 0
        return cpu, memory
    except (OSError, AttributeError, TypeError):
        return 0.0, 0


def run_bounded(argv, cwd, limits):
    limits = _validate_limits(limits)
    if not isinstance(argv, (list, tuple)) or not argv or any(not isinstance(x, str) for x in argv):
        raise DiscoveryError("argv must be a nonempty list of strings")
    cwd = Path(cwd).resolve(); cwd.mkdir(parents=True, exist_ok=True)
    cap = int(limits["disk_mb"] * 1024 * 1024)
    before = _tree_size(cwd)
    stdout_path, stderr_path = cwd / "stdout.log", cwd / "stderr.log"
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    preexec = None
    if os.name != "nt":
        def preexec():
            os.setsid()
            if resource is None:
                raise RuntimeError("POSIX rlimit unavailable")
            resource.setrlimit(resource.RLIMIT_AS, (int(limits["memory_mb"]*1024*1024),)*2)
            resource.setrlimit(resource.RLIMIT_CPU, (max(1, int(math.ceil(limits["cpu_seconds"]))),)*2)
    start = time.monotonic()
    try:
        proc = subprocess.Popen(argv, cwd=str(cwd), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=creationflags, preexec_fn=preexec)
    except (OSError, ValueError) as exc:
        raise DiscoveryError("Cannot start bounded process: " + str(exc)) from exc
    job = None
    if os.name == "nt":
        try:
            job = _WindowsJob(limits); job.assign(proc._handle)
        except Exception as exc:
            proc.kill(); proc.wait();
            if job: job.close()
            raise DiscoveryError("Required Windows Job Object unavailable: " + str(exc)) from exc
    state = {"cap": cap, "written": 0, "disk": False}
    peak_cpu, peak_memory = 0.0, 0
    lock = threading.Lock()
    threads = [threading.Thread(target=_reader, args=(proc.stdout, stdout_path, state, lock), daemon=True),
               threading.Thread(target=_reader, args=(proc.stderr, stderr_path, state, lock), daemon=True)]
    for thread in threads: thread.start()
    reason = None
    while proc.poll() is None:
        elapsed = time.monotonic() - start
        size = before + _tree_size(cwd)
        if state["disk"] or size > cap:
            reason = "DISK_LIMIT"
        elif os.name == "nt":
            cpu, memory = _windows_usage(proc._handle)
            peak_cpu, peak_memory = max(peak_cpu, cpu), max(peak_memory, memory)
            if cpu >= limits["cpu_seconds"]: reason = "CPU_LIMIT"
            elif memory >= limits["memory_mb"] * 1024 * 1024: reason = "MEMORY_LIMIT"
            elif elapsed >= limits["seconds"]: reason = "TIMEOUT"
        else:
            cpu, memory = _posix_usage(proc.pid)
            peak_cpu, peak_memory = max(peak_cpu, cpu), max(peak_memory, memory)
            if cpu >= limits["cpu_seconds"]: reason = "CPU_LIMIT"
            elif memory >= limits["memory_mb"] * 1024 * 1024: reason = "MEMORY_LIMIT"
            elif elapsed >= limits["seconds"]: reason = "TIMEOUT"
        if reason:
            if job: job.terminate()
            elif os.name != "nt":
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            else: proc.kill()
            break
        time.sleep(0.01)
    try: proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if job: job.terminate()
        else: proc.kill()
        proc.wait(timeout=2)
    for thread in threads: thread.join(timeout=1)
    if job: job.close()
    elapsed = time.monotonic() - start
    if reason is None and os.name != "nt" and proc.returncode is not None:
        if proc.returncode == -signal.SIGXCPU: reason = "CPU_LIMIT"
        elif peak_memory >= limits["memory_mb"] * 1024 * 1024: reason = "MEMORY_LIMIT"
    if reason is None and state["disk"]: reason = "DISK_LIMIT"
    if reason is None and os.name == "nt" and proc.returncode not in (0, None):
        # Job Object termination can race the final poll. Infer only from a
        # deliberately tight configured threshold; normal nonzero exits keep
        # their return code and no stop reason.
        if peak_memory >= limits["memory_mb"] * 1024 * 1024: reason = "MEMORY_LIMIT"
        elif peak_cpu >= limits["cpu_seconds"]: reason = "CPU_LIMIT"
    return {"returncode": proc.returncode, "stop_reason": reason,
            "elapsed_seconds": elapsed, "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path), "platform": platform.platform(),
            "limitations": ["No network or path sandbox; limits are process/resource governors"]}
