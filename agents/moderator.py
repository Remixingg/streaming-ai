import os
from uagents import Agent, Context, Protocol
from uagents.setup import fund_agent_if_low

from models.messaging import ModerationRequest, ModerationResponse
# from services.llm_clients import query_openai_moderator
from services.llm_clients import query_gemini_moderator 

MODERATOR_AGENT_SEED = os.getenv("MODERATOR_AGENT_SEED")
if not MODERATOR_AGENT_SEED:
    raise ValueError("Not found: MODERATOR_AGENT_SEED")

endpoints = {
    "default": {
        "url": "http://127.0.0.1:8000/submit",
        "weight": 1,
    }
}

agent = Agent(
    name="moderator_agent",
    seed=MODERATOR_AGENT_SEED,
    port=8000,
    endpoint=endpoints,
)

fund_agent_if_low(agent.wallet.address())

moderator_protocol = Protocol("ChatModeration")

@moderator_protocol.on_message(model=ModerationRequest, replies=ModerationResponse)
async def moderate_message(ctx: Context, sender: str, msg: ModerationRequest):
    ctx.logger.info(f"Received moderation request for text: '{msg.text}'")

    # change for diff LLM
    is_bad = query_gemini_moderator(msg.text)

    await ctx.send(sender, ModerationResponse(is_inappropriate=is_bad))
    ctx.logger.info(f"Sent response: is_inappropriate={is_bad}")

agent.include(moderator_protocol)