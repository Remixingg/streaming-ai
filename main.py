from dotenv import load_dotenv
import os

load_dotenv()

from agents.moderator import agent as moderator_agent
from agents.test_agent import agent as test_client_agent

if __name__ == "__main__":
    from uagents import Bureau
    bureau = Bureau()
    bureau.add(moderator_agent)
    bureau.add(test_client_agent)
    bureau.run()