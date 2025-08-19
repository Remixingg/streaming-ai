import os
import json
import httpx
import traceback
from dotenv import load_dotenv
from datetime import datetime
from uuid import uuid4
from uagents import Agent, Context, Protocol, Model
from uagents_core.contrib.protocols.chat import (
    ChatMessage, ChatAcknowledgement, TextContent, chat_protocol_spec
)
from uagents.setup import fund_agent_if_low

load_dotenv()

# ASI:One fallback (alt)
try:
    import google.generativeai as genai
except Exception:
    genai = None



# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
class Config:
    def __init__(self):
        self.MODERATOR_AGENT_SEED = os.getenv("MODERATOR_AGENT_SEED")
        self.ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY")
        self.ASI_ONE_URL = os.getenv("ASI_ONE_URL", "https://api.asi1.ai/v1/chat/completions")
        self.ASI_ONE_MODEL = os.getenv("ASI_ONE_MODEL", "asi1-mini")
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.DEBUG_ALLOW_NO_LLM = os.getenv("DEBUG_ALLOW_NO_LLM", "0") == "1"

    def validate(self):
        if not self.MODERATOR_AGENT_SEED:
            raise ValueError("Not found/set: MODERATOR_AGENT_SEED")
        if not self.ASI_ONE_API_KEY and not self.GEMINI_API_KEY:
            raise ValueError("Not found/set: ASI_ONE_API_KEY/GEMINI_API_KEY")

config = Config()
config.validate()



# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class ModerationRequest(Model):
    text: str

class ModerationResponse(Model):
    is_inappropriate: bool



# -----------------------------------------------------------------------------#
# Error Handling
# -----------------------------------------------------------------------------
def handle_http_error(e: httpx.HTTPStatusError):
    body_text = None
    try:
        body_text = (e.response.text) if e.response else ""
    except Exception:
        body_text = str(e.response.text) if e.response else ""
    raise RuntimeError(f"HTTP error occurred: {e.response.status_code if e.response else ''}: {body_text}") from e


def handle_network_error(e: Exception):
    raise RuntimeError(f"Network or timeout error occurred: {str(e)}") from e


def handle_json_error(resp: httpx.Response):
    text_raw = resp.text if hasattr(resp, "text") else "<no-body>"
    raise RuntimeError(f"Error parsing JSON response: {text_raw}")



# -----------------------------------------------------------------------------
# Classify
# -----------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a thoughtful, context-aware moderator for a fun, energetic live streaming platform. "
    "Your goal is to protect the community from truly harmful content while allowing for playful banter and jokes. "
    "You must classify the user's message into one of two categories:\n\n"
    "1. **Playful Banter / Mild Trash Talk (Acceptable):** This includes things like 'noob', 'L', 'get rekt', 'you're so bad at this game lol', 'dummy', 'stupid play'. These are generally acceptable in a gaming context.\n\n"
    "2. **Truly Harmful Content (Unacceptable):** This includes slurs (e.g., the r-slur, the aut-slur, etc.), harassment, severe personal attacks, encouraging self-harm, racist or sexist remarks, and explicit sexual language. This is never acceptable.\n\n"
    "Now, analyze the following user message. Based on these definitions, is the message **Truly Harmful**? "
    "Respond with only one word: 'YES' if it is Truly Harmful, or 'NO' if it is not."
)

harmful_words = [
    "hate", "slut", "bitch", "bastard", "whore", "motherfucker", "cunt", "nigga", "nigger", "fag", "queer", "retard", "autistic", "kill yourself", "suicide", "rape", "pedophile", "molest", "slavery", "racist", "sexist", "abuse", "incest", "violence", "terrorist", "nazi", "neo-nazi", "antisemite", "blacklist", "sexism", "homophobia", "bigot", "feminazi", "rape culture"
]

def contains_harmful_words(text):
    return any(word in text.lower() for word in harmful_words)

async def classify_message(text: str) -> bool:
    if contains_harmful_words(text):
        return True
    if config.ASI_ONE_API_KEY:
        return await classify_with_asione(text)
    if config.GEMINI_API_KEY and genai:
        return await classify_with_gemini(text)
    return False


async def classify_with_asione(text: str) -> bool:
    headers = {
        "Authorization": f"Bearer {config.ASI_ONE_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": config.ASI_ONE_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post(config.ASI_ONE_URL, headers=headers, json=body)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            handle_http_error(e)
        except Exception as e:
            handle_network_error(e)

        try:
            data = resp.json()
        except Exception as e:
            handle_json_error(resp)

    return parse_response(data)


async def classify_with_gemini(text: str) -> bool:
    if not genai:
        raise RuntimeError("Gemini API is not available")
    
    model = genai.GenerativeModel("gemini-1.5-flash-latest")
    prompt = SYSTEM_PROMPT + "\n\nUSER MESSAGE: " + text
    
    try:
        response = await model.generate_content_async(prompt)
        raw = response.text if hasattr(response, "text") else str(response)
    except Exception as e:
        raise RuntimeError(f"Gemini call failed: {e}") from e

    return parse_response(raw)


def parse_response(raw):
    normalized = ""
    if isinstance(raw, dict):
        if 'choices' in raw:
            normalized = raw['choices'][0]['message']['content']
        elif 'output' in raw:
            normalized = raw['output']

    if isinstance(normalized, str):
        normalized = normalized.strip().upper()
    if normalized.startswith("YES"):
        return True
    if normalized.startswith("NO"):
        return False
    return False



# -----------------------------------------------------------------------------
# Agent Creation
# -----------------------------------------------------------------------------
def create_moderator_agent(seed: str) -> Agent:
    if not seed:
        raise ValueError("Not found/set: MODERATOR_AGENT_SEED")

    agent = Agent(
        name="moderator_agent",
        seed=seed,
        port=8000,
        mailbox=True,
        publish_agent_details=True,
        readme_path="moderator_README.md",
    )

    try:
        fund_agent_if_low(agent.wallet.address())
    except Exception:
        print("fund_agent_if_low failed or not available in this environment")

    moderation_protocol = Protocol("ChatModeration")

    @moderation_protocol.on_message(model=ModerationRequest, replies=ModerationResponse)
    async def moderate_message(ctx: Context, sender: str, msg: ModerationRequest):
        ctx.logger.info(f"[moderator] Received moderation request for text: '{msg.text}'")
        is_bad = await classify_message(msg.text)
        resp = ModerationResponse(is_inappropriate=is_bad)
        await ctx.send(sender, resp)
        ctx.logger.info(f"[moderator] Sent response to caller: is_inappropriate={is_bad}")

    chat_proto = Protocol(spec=chat_protocol_spec)

    @chat_proto.on_message(ChatMessage)
    async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
        await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id))

        user_text = None
        for item in msg.content:
            if isinstance(item, TextContent):
                user_text = item.text
                break

        is_bad = await classify_message(user_text) if user_text else False
        reply = f"Inappropriate: {'YES' if is_bad else 'NO'}"
        await ctx.send(sender, ChatMessage(
            timestamp=datetime.utcnow(),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=reply)],
        ))

    @chat_proto.on_message(ChatAcknowledgement)
    async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
        ctx.logger.info(
            f"Received chat acknowledgement from {sender} for {msg.acknowledged_msg_id}"
        )

    @agent.on_rest_post("/moderate", ModerationRequest, ModerationResponse)
    async def rest_moderate(ctx: Context, req: ModerationRequest) -> ModerationResponse:
        is_bad = await classify_message(req.text or "")
        return ModerationResponse(is_inappropriate=is_bad)
    
    try:
        agent.include(moderation_protocol)
        agent.include(chat_proto, publish_manifest=True)
    except Exception as e:
        print("Error including protocol:")
        traceback.print_exc()

    return agent



# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------
def main():
    agent = create_moderator_agent(seed=config.MODERATOR_AGENT_SEED)
    print("Starting moderator agent... (listening on port 8000)")
    agent.run()


if __name__ == "__main__":
    main()
