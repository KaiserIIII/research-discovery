"""Real-process regressions: dropping a limit must break one of these cases."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from rd.core import DiscoveryError
try:
    from rd.limits import run_bounded, resources
    IMPORT_ERROR = None
except ImportError as exc:
    IMPORT_ERROR = str(exc)


class LimitTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNone(IMPORT_ERROR, 'Missing implementation: ' + str(IMPORT_ERROR))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_code(self, code, **patch):
        caps = dict(seconds=3, memory_mb=128, disk_mb=2, cpu_seconds=2)
        caps.update(patch)
        return run_bounded([sys.executable, '-I', '-c', code], self.root / 'run', caps)

    def test_completed_command_captures_stderr_and_nonzero_exit(self):
        result = self.run_code('import sys; print("diagnostic", file=sys.stderr); sys.exit(7)')
        self.assertEqual(result['returncode'], 7)
        self.assertIsNone(result['stop_reason'])
        self.assertIn('diagnostic', Path(result['stderr_path']).read_text())

    def test_stdout_is_capped_and_disk_stop_is_reported(self):
        result = self.run_code('import sys,time; sys.stdout.write("x"*2000000); sys.stdout.flush(); time.sleep(2)', disk_mb=0.1)
        self.assertEqual(result['stop_reason'], 'DISK_LIMIT')
        self.assertLessEqual(sum(p.stat().st_size for p in (self.root/'run').rglob('*') if p.is_file()), 104857)

    def test_memory_limit_rejects_real_allocation(self):
        result = self.run_code('items=[]\nwhile True: items.append(bytearray(8*1024*1024))', memory_mb=96)
        self.assertEqual(result['stop_reason'], 'MEMORY_LIMIT')
        self.assertLess(result['elapsed_seconds'], 3)

    def test_cpu_limit_stops_busy_loop_before_wall_limit(self):
        result = self.run_code('while True: pass', cpu_seconds=0.2)
        self.assertEqual(result['stop_reason'], 'CPU_LIMIT')
        self.assertLess(result['elapsed_seconds'], 2)

    def test_wall_limit_terminates_process_tree(self):
        code = 'import subprocess,sys,time; p=subprocess.Popen([sys.executable,"-I","-c","import time; time.sleep(10)"]); print(p.pid, flush=True); time.sleep(10)'
        result = self.run_code(code, seconds=0.35)
        self.assertEqual(result['stop_reason'], 'TIMEOUT')
        pid = int(Path(result['stdout_path']).read_text().strip())
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            api = ctypes.WinDLL('kernel32', use_last_error=True)
            api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            api.OpenProcess.restype = wintypes.HANDLE
            api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            api.WaitForSingleObject.restype = wintypes.DWORD
            api.CloseHandle.argtypes = [wintypes.HANDLE]
            api.CloseHandle.restype = wintypes.BOOL
            handle = api.OpenProcess(0x00100000, False, pid)
            if handle:
                try: self.assertEqual(api.WaitForSingleObject(handle, 1000), 0)
                finally: api.CloseHandle(handle)
        else:
            # An unreaped zombie is terminated; its former parent cannot reap it.
            status = Path('/proc') / str(pid) / 'stat'
            if status.exists(): self.assertEqual(status.read_text().split()[2], 'Z')
            else:
                with self.assertRaises(ProcessLookupError): os.kill(pid, 0)

    def test_probe_reports_real_available_ram_and_disk(self):
        probe = resources(self.root)
        self.assertGreater(probe['available_memory_bytes'], 0)
        self.assertGreater(probe['disk_free_bytes'], 0)
        self.assertFalse(probe['gpu_used'])
        self.assertIn('gpu', probe)

    def test_invalid_or_excessive_limits_never_spawn(self):
        for patch in ({'seconds': -1}, {'cpu_seconds': float('nan')}, {'memory_mb': True}, {'disk_mb': 0}):
            with self.subTest(patch=patch), self.assertRaises(DiscoveryError):
                self.run_code('pass', **patch)


if __name__ == '__main__': unittest.main()
