import os
from dotenv import load_dotenv
from agents.moderator import create_moderator_agent

load_dotenv()

if __name__ == "__main__":
    MODERATOR_AGENT_SEED = os.getenv("MODERATOR_AGENT_SEED")
    if not MODERATOR_AGENT_SEED:
        raise ValueError("Not found: MODERATOR_AGENT_SEED")
    
    agent = create_moderator_agent(seed=MODERATOR_AGENT_SEED)    
    print("Starting MODERATOR agent...")
    agent.run()