"""
scripts/reset_demo.py
---------------------
Resets AgentHide warehouse inventory and active disruptions back to the pristine baseline.
Run with: python scripts/reset_demo.py
"""

import sys
import os

# Add root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.risk_tools import clear_disruptions


def reset():
    print("[AgentHide] Resetting demo state...")
    clear_disruptions()
    print("[OK] All active disruptions cleared.")
    print("[OK] Baseline inventory ready for demonstration.")


if __name__ == "__main__":
    reset()
