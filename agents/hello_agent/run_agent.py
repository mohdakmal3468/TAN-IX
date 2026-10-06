"""
agents/hello_agent/run_agent.py
-------------------------------
Direct runner script for the Hello Practice Agent.
Run directly with:
    python agents/hello_agent/run_agent.py

Demonstrates:
1. Tool execution (add_numbers)
2. Agent structure inspection (instruction, model, tools)
3. Running with Google ADK CLI commands
"""

import os
import sys

# Ensure root directory is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# Make sure GOOGLE_API_KEY is synchronized with GEMINI_API_KEY if present
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

from agents.hello_agent.agent import agent, add_numbers


def main():
    print("=" * 70)
    print("GOOGLE ADK: HELLO PRACTICE AGENT")
    print("=" * 70)

    # 1. Inspect the Agent's Core Components
    print(f"\n1. AGENT IDENTITY:")
    print(f"   • Name        : {agent.name}")
    print(f"   • Model       : {agent.model}")
    print(f"   • Description : {agent.description}")

    print(f"\n2. INSTRUCTION (Prompt / Job Description):")
    print(f"   ------------------------------------------------------------")
    for line in agent.instruction.strip().split("\n"):
        print(f"   {line}")
    print(f"   ------------------------------------------------------------")

    print(f"\n3. REGISTERED TOOLS:")
    for tool_fn in agent.tools:
        print(f"   • Function Name: {tool_fn.__name__}")
        print(f"   • Docstring    : {tool_fn.__doc__.strip().splitlines()[0]}")

    # 2. Test the Tool directly in Python
    print(f"\n4. DIRECT TOOL TEST:")
    num1 = 45.5
    num2 = 54.5
    res = add_numbers(num1, num2)
    print(f"   Verified: add_numbers({num1}, {num2}) = {res}")

    # 3. Explain how to run with ADK CLI and Web UI
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    print("\n" + "=" * 70)
    print("HOW TO RUN THIS AGENT WITH GOOGLE ADK")
    print("=" * 70)

    if not api_key or api_key == "your_gemini_api_key_here":
        print("[!] Note: Set your GEMINI_API_KEY in .env to enable live LLM reasoning.")
        print("    Get a free key from: https://aistudio.google.com/")
    else:
        print("[✓] GEMINI_API_KEY is configured in your environment!")

    print("\nOption A: Run single question via ADK CLI:")
    print('   python -m google.adk.cli run agents/hello_agent "What is 125 plus 375?" --in_memory')

    print("\nOption B: Run interactive terminal chat via ADK CLI:")
    print('   python -m google.adk.cli run agents/hello_agent --in_memory')

    print("\nOption C: Launch the full ADK Web Dev UI (browser chat & tool inspector):")
    print('   python -m google.adk.cli web agents')
    print('   -> Open http://localhost:8000 (or the port displayed in terminal)')
    print("=" * 70)


if __name__ == "__main__":
    main()
