"""Portable measurement helpers shared by the bench scripts (Windows, Linux, macOS).

Peak memory: Windows exposes ``peak_wset`` through psutil; Linux and macOS report the process's peak
resident size through ``resource.getrusage`` (kilobytes on Linux, bytes on macOS). Both are whole-process
peaks, so they include interpreter, libraries, model and working memory.
"""
import platform
import subprocess
import sys

import psutil

MIB = 1024 * 1024  # memory is reported in MiB (1,048,576 bytes), not decimal MB


def memory_mib() -> tuple[float, float]:
    """(current resident, peak resident) in MiB for this process."""
    info = psutil.Process().memory_info()
    peak = getattr(info, "peak_wset", None)
    if peak is None:
        try:
            import resource

            raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            peak = raw if sys.platform == "darwin" else raw * 1024
        except ImportError:  # no resource module and no peak_wset: report current as a lower bound
            peak = info.rss
    return round(info.rss / MIB, 1), round(peak / MIB, 1)


def pin_to_one_core() -> str:
    """Pin this process to one CPU where the OS supports it; return a description for the report."""
    proc = psutil.Process()
    try:
        cpu = proc.cpu_affinity()[0]  # first CPU this process may already use
        proc.cpu_affinity([cpu])
        return f"pinned to CPU {cpu}"
    except (AttributeError, NotImplementedError, OSError):  # e.g. macOS has no affinity API
        return "NOT pinned (OS has no affinity API); thread counts are still limited to 1"


def os_name() -> str:
    """OS name WITHOUT ``platform.system()``: on Windows with Python 3.12 that call queries WMI and adds about 5 MiB to
    the process working set (measured), which inflated every memory figure this benchmark reported until it was removed."""
    return {"win32": "Windows", "linux": "Linux", "darwin": "macOS"}.get(sys.platform, sys.platform)


def cpu_model() -> str:
    """CPU name for the report, read without anything that raises the measured process's memory: the Windows registry
    (no PowerShell subprocess, no ``platform`` calls), /proc/cpuinfo, or sysctl."""
    system = os_name()
    if system == "Windows":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            pass  # fall through to the last resort below
    try:
        if system == "Linux":
            with open("/proc/cpuinfo", encoding="utf-8") as handle:
                for line in handle:
                    if line.lower().startswith("model name"):
                        return line.split(":", 1)[1].strip()
        if system == "macOS":
            out = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, check=True)
            return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        pass
    return platform.processor() or "unknown"  # last resort; may itself cost memory on Windows
