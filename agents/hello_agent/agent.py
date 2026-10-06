"""
agents/hello_agent/agent.py
---------------------------
A beginner-friendly practice agent built with Google ADK (Agent Development Kit)
and Gemini 3.1 Flash.

================================================================================
                    CORE AGENT CONCEPTS EXPLAINED FOR BEGINNERS
================================================================================

1. WHAT IS AN INSTRUCTION?
   - The Instruction (also known as the System Prompt) is the AI's "job description"
     and "personality guide".
   - It tells the model:
       * Who it is (e.g. "You are a helpful math assistant").
       * What rules it must follow (e.g. "Always be polite and explain your steps").
       * How to handle tools (e.g. "Whenever asked to add numbers, you MUST use the
         add_numbers tool rather than doing mental math").

2. WHAT IS A TOOL?
   - Large Language Models (LLMs) are great with words, but they can make arithmetic
     mistakes or hallucinate facts because they predict the next likely word.
   - A Tool is a normal Python function that gives the AI a "real-world superpower".
   - Instead of guessing 3847 + 9182, the AI recognizes that it has a tool named
     'add_numbers', prepares the arguments {"a": 3847, "b": 9182}, executes the
     Python function, and receives the exact mathematical truth!

3. WHAT IS AN AGENT?
   - An Agent is the autonomous coordinator that ties everything together:
       [LLM Model (Brain)] + [Instruction (Goal)] + [Tools (Hands & Calculator)]
   - When a user asks a question, the Agent:
       Step A: Reads the question.
       Step B: Thinks autonomously about which tool to call.
       Step C: Calls the tool with the right inputs.
       Step D: Takes the tool's output and formats a friendly final response.
================================================================================
"""

import os
from google.adk import Agent
from dotenv import load_dotenv

# Load environment variables (such as GEMINI_API_KEY)
load_dotenv()

# We specify Gemini model: user requested Gemini 3.1 Flash.
# You can override this in your .env with GEMINI_MODEL=gemini-2.5-flash or gemini-3.1-flash
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# ==============================================================================
# TOOL DEFINITION
# ==============================================================================
# In Google ADK, any standard Python function with type hints and a docstring
# can be used as a Tool! The docstring tells Gemini *what* the tool does.
# ==============================================================================

def add_numbers(a: float, b: float) -> float:
    """Adds two numbers together and returns the exact mathematical sum.

    Args:
        a: The first number (integer or decimal).
        b: The second number (integer or decimal).

    Returns:
        The sum of a and b.
    """
    print(f"\n[Tool Execution] add_numbers called with a={a}, b={b}")
    result = a + b
    print(f"[Tool Execution] Computed result: {result}\n")
    return result


# ==============================================================================
# AGENT DEFINITION
# ==============================================================================
# Here we assemble the Agent using Google ADK's `Agent` class.
# ==============================================================================

agent = Agent(
    name="hello_agent",
    model=MODEL_NAME,
    description="A friendly beginner practice agent that adds numbers using the add_numbers tool.",
    instruction=(
        "You are 'HelloMathAgent', a friendly and encouraging AI tutor built with Google ADK.\n"
        "Your mission is to help users with addition questions.\n"
        "RULES:\n"
        "1. Whenever the user asks you to add two or more numbers, you MUST call the "
        "`add_numbers` tool to compute the answer.\n"
        "2. Do NOT guess the answer yourself; always rely on the tool output.\n"
        "3. Explain the answer cheerfully and briefly in simple words."
    ),
    tools=[add_numbers]
)

# Export as root_agent as well (standard ADK discovery convention)
root_agent = agent
