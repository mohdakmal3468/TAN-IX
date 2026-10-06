"""
hello_agent package initialization.
Exports agent and root_agent for Google ADK discovery.
"""

from agents.hello_agent.agent import agent, root_agent, add_numbers

__all__ = ["agent", "root_agent", "add_numbers"]
