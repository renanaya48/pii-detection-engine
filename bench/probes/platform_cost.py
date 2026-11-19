"""How much does a harmless-looking call raise this process's working set? (Windows, Python 3.12)

    python bench/probes/platform_cost.py sys.platform | platform.python_version | winreg | platform.system

Each call must run in its own fresh process. Result that mattered: ``platform.system()`` (and ``platform.uname()``) query WMI
and add about 5 MiB to the working set, while ``sys.platform`` and a registry read cost nothing. The benchmark's header used
``platform.system()`` and so inflated every memory figure it reported until it was replaced (see bench/_env.py).
"""
import sys

import psutil

MIB = 1 << 20


def working_set() -> float:
    return psutil.Process().memory_info().rss / MIB


def main() -> None:
    call = sys.argv[1] if len(sys.argv) > 1 else ""
    before = working_set()
    if call == "platform.system":
        import platform

        platform.system()
    elif call == "platform.python_version":
        import platform

        platform.python_version()
    elif call == "winreg":
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            winreg.QueryValueEx(key, "ProcessorNameString")
    elif call == "sys.platform":
        sys.platform.startswith("win")
    else:
        raise SystemExit(__doc__)
    after = working_set()
    print(f"{call:<26} working set {before:5.1f} -> {after:5.1f} MiB  ({after - before:+.1f})")


if __name__ == "__main__":
    main()
