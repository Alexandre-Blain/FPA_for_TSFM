"""Native Windows process-tree containment, including venv redirector children."""
from __future__ import annotations

import ctypes
import os
import subprocess
import time


class WindowsJobProcess:
    def __init__(self, command, cwd, env, log, memory_limit=None):
        if os.name != "nt":
            raise RuntimeError("Windows Job Objects require native Windows")
        import _winapi
        import msvcrt
        from ctypes import wintypes as w

        self.api = _winapi
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.returncode = None
        self._handle = self.job = None

        class BasicLimit(ctypes.Structure):
            _fields_ = [("per_process_time", ctypes.c_longlong), ("per_job_time", ctypes.c_longlong),
                        ("flags", w.DWORD), ("min_working", ctypes.c_size_t), ("max_working", ctypes.c_size_t),
                        ("active_process_limit", w.DWORD), ("affinity", ctypes.c_size_t),
                        ("priority", w.DWORD), ("scheduling", w.DWORD)]

        class IoCounters(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

        class ExtendedLimit(ctypes.Structure):
            _fields_ = [("basic", BasicLimit), ("io", IoCounters), ("process_memory_limit", ctypes.c_size_t),
                        ("job_memory_limit", ctypes.c_size_t), ("peak_process_memory", ctypes.c_size_t),
                        ("peak_job_memory", ctypes.c_size_t)]

        class Accounting(ctypes.Structure):
            _fields_ = [(n, ctypes.c_longlong) for n in ("user", "kernel", "period_user", "period_kernel")] + [
                (n, w.DWORD) for n in ("faults", "total_processes", "active_processes", "terminated_processes")]

        self.ExtendedLimit, self.Accounting = ExtendedLimit, Accounting
        for name, args, result in (
            ("CreateJobObjectW", [ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
            ("SetInformationJobObject", [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            ("QueryInformationJobObject", [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p], w.BOOL),
            ("AssignProcessToJobObject", [w.HANDLE, w.HANDLE], w.BOOL),
            ("TerminateJobObject", [w.HANDLE, w.UINT], w.BOOL),
            ("ResumeThread", [w.HANDLE], w.DWORD),
        ):
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = args, result
        self.job = self.kernel.CreateJobObjectW(None, None)
        if not self.job:
            raise ctypes.WinError(ctypes.get_last_error())
        limit = ExtendedLimit()
        limit.basic.flags = 0x2000  # Always kill descendants when the supervisor closes.
        if memory_limit is not None:
            limit.basic.flags |= 0x100 | 0x200
            limit.process_memory_limit = limit.job_memory_limit = int(memory_limit)
        if not self.kernel.SetInformationJobObject(self.job, 9, ctypes.byref(limit), ctypes.sizeof(limit)):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())
        thread = None
        try:
            with open(os.devnull, "rb") as stdin:
                out_handle, in_handle = msvcrt.get_osfhandle(log.fileno()), msvcrt.get_osfhandle(stdin.fileno())
                os.set_handle_inheritable(out_handle, True)
                os.set_handle_inheritable(in_handle, True)
                startup = subprocess.STARTUPINFO()
                startup.dwFlags = subprocess.STARTF_USESTDHANDLES
                startup.hStdOutput = startup.hStdError = out_handle
                startup.hStdInput = in_handle
                try:
                    process, thread, self.pid, _ = _winapi.CreateProcess(
                        command[0], subprocess.list2cmdline(command), None, None, True,
                        subprocess.CREATE_NO_WINDOW | 0x4, env, str(cwd), startup)
                    self._handle = process
                finally:
                    os.set_handle_inheritable(out_handle, False)
                    os.set_handle_inheritable(in_handle, False)
            # Suspension prevents the redirector from spawning an uncontained child.
            if not self.kernel.AssignProcessToJobObject(self.job, self._handle):
                raise ctypes.WinError(ctypes.get_last_error())
            if self.kernel.ResumeThread(thread) == 0xffffffff:
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            if self._handle is not None:
                _winapi.TerminateProcess(self._handle, 1)
            self.close()
            raise
        finally:
            if thread is not None:
                _winapi.CloseHandle(thread)

    def _query(self, kind, structure):
        value = structure()
        if not self.kernel.QueryInformationJobObject(self.job, kind, ctypes.byref(value), ctypes.sizeof(value), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return value

    def peak_job_memory(self):
        return int(self._query(9, self.ExtendedLimit).peak_job_memory)

    def active_processes(self):
        return int(self._query(1, self.Accounting).active_processes)

    def poll(self):
        code = self.api.GetExitCodeProcess(self._handle)
        if code == self.api.STILL_ACTIVE or self.active_processes():
            return None
        self.returncode = code if code < 2 ** 31 else code - 2 ** 32
        return self.returncode

    def kill(self):
        if not self.kernel.TerminateJobObject(self.job, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    def wait(self):
        while self.poll() is None:
            time.sleep(.02)
        return self.returncode

    def close(self):
        for name in ("job", "_handle"):
            handle = getattr(self, name, None)
            if handle is not None:
                self.api.CloseHandle(handle)
                setattr(self, name, None)
