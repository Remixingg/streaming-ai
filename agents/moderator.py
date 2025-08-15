from uagents import Agent, Context, Protocol
from uagents.setup import fund_agent_if_low
from models.messaging import ModerationRequest, ModerationResponse
from services.llm_clients import query_gemini_moderator

def create_moderator_agent(seed: str) -> Agent:

    endpoints = {
        "default": {
            "url": "http://127.0.0.1:8000/submit",
            "weight": 1,
        }
    }

    agent = Agent(
        name="moderator_agent",
        seed=seed,
        port=8000,
        endpoint=endpoints,
    )

    fund_agent_if_low(agent.wallet.address())

    moderator_protocol = Protocol("ChatModeration")

    @moderator_protocol.on_message(model=ModerationRequest, replies=ModerationResponse)
    async def moderate_message(ctx: Context, sender: str, msg: ModerationRequest):
        ctx.logger.info(f"Received moderation request for text: '{msg.text}'")
        is_bad = query_gemini_moderator(msg.text)
        await ctx.send(sender, ModerationResponse(is_inappropriate=is_bad))
        ctx.logger.info(f"Sent response: is_inappropriate={is_bad}")

    agent.include(moderator_protocol)
    
    return agent