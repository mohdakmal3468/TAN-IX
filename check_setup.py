"""
check_setup.py
--------------
Validates the Python environment for AgentHide:
1. Verifies Python is 3.10+
2. Checks all required packages and prints their installed versions.
"""

import sys
import importlib
import importlib.metadata

REQUIRED_PACKAGES = [
    ("google-adk", "google.adk"),
    ("google-cloud-firestore", "google.cloud.firestore"),
    ("google-cloud-bigquery", "google.cloud.bigquery"),
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("streamlit", "streamlit"),
    ("python-dotenv", "dotenv"),
    ("pandas", "pandas"),
    ("requests", "requests")
]


def check_python_version() -> bool:
    """Verifies Python version is at least 3.10."""
    major = sys.version_info.major
    minor = sys.version_info.minor
    micro = sys.version_info.micro
    version_str = f"{major}.{minor}.{micro}"

    print("=" * 60, flush=True)
    print("AgentHide Python Environment Verification", flush=True)
    print("=" * 60, flush=True)
    print(f"Active Python Executable: {sys.executable}", flush=True)
    print(f"Detected Python Version : {version_str}", flush=True)

    if major == 3 and minor >= 10:
        print("[OK] Python version is 3.10+ compatible.", flush=True)
        return True
    else:
        print(f"[FAIL] Python 3.10+ required. Current version is {version_str}.", flush=True)
        return False


def check_packages() -> bool:
    """Checks each required package distribution and module import."""
    print("-" * 60, flush=True)
    print(f"{'Package Name':<28} {'Installed Version':<18} {'Status'}", flush=True)
    print("-" * 60, flush=True)

    all_passed = True

    for dist_name, module_name in REQUIRED_PACKAGES:
        # Check distribution metadata version
        try:
            version = importlib.metadata.version(dist_name)
        except importlib.metadata.PackageNotFoundError:
            version = "NOT FOUND"

        # Check module importability
        try:
            importlib.import_module(module_name)
            import_ok = True
        except Exception:
            import_ok = False

        if version != "NOT FOUND" and import_ok:
            status = "[OK]"
        else:
            status = "[FAIL]"
            all_passed = False

        print(f"{dist_name:<28} {version:<18} {status}", flush=True)

    print("-" * 60, flush=True)
    return all_passed


def main():
    py_ok = check_python_version()
    pkg_ok = check_packages()

    print("=" * 60, flush=True)
    if py_ok and pkg_ok:
        print("[SUCCESS] All dependencies verified! Your environment is ready.", flush=True)
    else:
        print("[WARNING] Some dependencies are missing or incompatible.", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
