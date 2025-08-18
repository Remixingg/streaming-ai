import os
import json
from dotenv import load_dotenv
from datetime import datetime
from uuid import uuid4

load_dotenv()

import httpx
from uagents import Agent, Context, Protocol, Model
from uagents_core.contrib.protocols.chat import (
    ChatMessage, ChatAcknowledgement, TextContent,
    EndSessionContent, StartSessionContent, chat_protocol_spec
)
from uagents.setup import fund_agent_if_low
import traceback

# ASI:One fallback (alt)
try:
    import google.generativeai as genai
except Exception:
    genai = None



# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
MODERATOR_AGENT_SEED = os.getenv("MODERATOR_AGENT_SEED")
ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY")
ASI_ONE_URL = os.getenv("ASI_ONE_URL", "https://api.asi1.ai/v1/chat/completions")
ASI_ONE_MODEL = os.getenv("ASI_ONE_MODEL", "asi1-mini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ICP_URL = os.getenv("ICP_URL")  # e.g. https://<canister_id>.ic0.app/moderation
# AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY")
DEBUG_ALLOW_NO_LLM = os.getenv("DEBUG_ALLOW_NO_LLM", "0") == "1"



# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class ModerationRequest(Model):
    text: str

class ModerationResponse(Model):
    is_inappropriate: bool



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

if genai and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception:
        pass

async def classify_with_asione(text: str) -> (bool):

    if ASI_ONE_API_KEY:
        raise RuntimeError("ASI:One API key not configured")

    headers = {
        "Authorization": f"Bearer {ASI_ONE_API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": ASI_ONE_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post(ASI_ONE_URL, headers=headers, json=body)
            # This will raise httpx.HTTPStatusError for 4xx/5xx after .raise_for_status()
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            # include response text for debugging
            body_text = None
            try:
                body_text = (await e.response.aread()).decode(errors="ignore") if e.response else ""
            except Exception:
                body_text = str(e.response.text) if e.response is not None else ""
            raise RuntimeError(f"ASI:One HTTP error {e.response.status_code if e.response else ''}: {body_text}") from e
        except Exception as e:
            # network / timeout etc
            raise RuntimeError(f"Error calling ASI:One: {e}") from e

        # parse JSON safely
        try:
            data = resp.json()
        except Exception as e:
            # include raw text for debugging when JSON parse fails
            text_raw = resp.text if hasattr(resp, "text") else "<no-body>"
            raise RuntimeError(f"ASI:One response not JSON: {text_raw}") from e

    # Try to extract assistant content
    explanation = ""
    try:
        explanation = data["choices"][0]["message"]["content"].strip()
    except Exception:
        # fallbacks
        if isinstance(data, dict):
            if "result" in data:
                explanation = str(data["result"])
            elif "output" in data:
                if isinstance(data["output"], str):
                    explanation = data["output"]
                elif isinstance(data["output"], dict) and "text" in data["output"]:
                    explanation = data["output"]["text"]
            elif "choices" in data and len(data["choices"]) > 0:
                first = data["choices"][0]
                if isinstance(first, dict):
                    if "text" in first:
                        explanation = str(first["text"])
                    elif "message" in first and isinstance(first["message"], dict) and "content" in first["message"]:
                        explanation = str(first["message"]["content"])
        if not explanation:
            explanation = json.dumps(data)

    normalized = explanation.strip().upper()
    # interpret YES/NO
    first_line = normalized.splitlines()[0] if normalized else ""
    if first_line.startswith("YES") or first_line.split()[:1] == ["YES"]:
        is_bad = True
    elif first_line.startswith("NO") or first_line.split()[:1] == ["NO"]:
        is_bad = False
    else:
        is_bad = "YES" in normalized

    return is_bad

async def classify_with_gemini(text: str) -> (bool):
    if not genai or not GEMINI_API_KEY:
        raise RuntimeError("Gemini not available or GEMINI_API_KEY missing")
    model = genai.GenerativeModel("gemini-1.5-flash-latest")
    prompt = SYSTEM_PROMPT + "\n\nUSER MESSAGE: " + text
    try:
        response = await model.generate_content_async(prompt)
        raw = response.text if hasattr(response, "text") else str(response)
    except Exception as e:
        raise RuntimeError(f"Gemini call failed: {e}") from e

    # Normalize answer text -> boolean
    normalized = raw.strip().upper()
    # Look for an explicit YES/NO at the start or anywhere
    if normalized.startswith("YES") or normalized.split()[0] == "YES" or " YES " in f" {normalized} ":
        return True
    if normalized.startswith("NO") or normalized.split()[0] == "NO" or " NO " in f" {normalized} ":
        return False

    # If unsure, fallback to conservative default (not harmful)
    return False

harmful_words = [
    "hate", "slut", "bitch", "bastard", "whore", "motherfucker", "cunt", "nigger", "fag", "queer", 
    "retard", "autistic", "kill yourself", "suicide", "rape", "pedophile", "molest", "slavery", 
    "racist", "sexist", "abuse", "incest", "violence", "terrorist", "nazi", "neo-nazi", "antisemite",
    "blacklist", "sexism", "homophobia", "bigot", "feminazi", "rape culture"
]

# Function to check for harmful words
def contains_harmful_words(text):
    return any(word in text.lower() for word in harmful_words)



# -----------------------------------------------------------------------------
# Agent Creation
# -----------------------------------------------------------------------------
def create_moderator_agent(seed: str) -> Agent:
    if not seed:
        raise ValueError("MODERATOR_AGENT_SEED not provided")

    agent = Agent(
        name="moderator_agent",
        seed=seed,
        port=8000,
        mailbox=True,
        publish_agent_details=True,
        readme_path="README.md",
    )

    try:
        fund_agent_if_low(agent.wallet.address())
    except Exception:
        print("fund_agent_if_low failed or not available in this environment")

    moderation_protocol = Protocol("ChatModeration")

    @moderation_protocol.on_message(model=ModerationRequest, replies=ModerationResponse)
    async def moderate_message(ctx: Context, sender: str, msg: ModerationRequest):
        ctx.logger.info(f"[moderator] Received moderation request for text: '{msg.text}'")
        is_bad = False
        tried_methods = []
        try:
            if contains_harmful_words(msg.text):
                is_bad = True
                ctx.logger.info(f"[moderator] Message contains harmful words, classified as harmful.")
            else:
                if not ASI_ONE_API_KEY:
                    tried_methods.append("ASI:One")
                    is_bad = await classify_with_asione(msg.text)
                elif GEMINI_API_KEY and genai:
                    tried_methods.append("Gemini")
                    is_bad = await classify_with_gemini(msg.text)
                else:
                    tried_methods.append("None")
                    is_bad = False
                    if not DEBUG_ALLOW_NO_LLM:
                        ctx.logger.error("No LLM API keys found and DEBUG_ALLOW_NO_LLM is false.")
        except Exception as e:
            ctx.logger.error(f"Error during classification ({tried_methods}): {repr(e)}")
            ctx.logger.error(traceback.format_exc())
            is_bad = False

        # response
        try:
            resp = ModerationResponse(is_inappropriate=is_bad)
            await ctx.send(sender, resp)
            ctx.logger.info(f"[moderator] Sent response to caller: is_inappropriate={is_bad}")
        except Exception as e:
            ctx.logger.error(f"[moderator] Failed to send response to caller: {e}")

        # ICP
        if ICP_URL:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    payload = {
                        "text": msg.text,
                        "is_inappropriate": bool(is_bad),
                        "source_agent": agent.wallet.address(),
                    }
                    # Try POSTing raw JSON. Your Motoko canister should expose an HTTP handler that accepts JSON.
                    r = await client.post(ICP_URL, json=payload)
                    if r.status_code >= 200 and r.status_code < 300:
                        ctx.logger.info("[moderator] Successfully posted moderation result to ICP canister.")
                    else:
                        ctx.logger.warning(f"[moderator] Posting to ICP returned status {r.status_code}: {r.text}")
            except Exception as e:
                ctx.logger.error(f"[moderator] Error sending moderation result to ICP: {e}")
        else:
            ctx.logger.debug("ICP_URL not configured; skipping ICP logging.")

    chat_proto = Protocol(spec=chat_protocol_spec)

    @chat_proto.on_message(ChatMessage)
    async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
        await ctx.send(sender, ChatAcknowledgement(
            timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id
        ))

        user_text = None
        for item in msg.content:
            if isinstance(item, TextContent):
                user_text = item.text
                break
            if isinstance(item, StartSessionContent):
                ctx.logger.info("Chat session started")

        if not user_text:
            reply = "Please send text content to classify."
        else:
            try:
                is_bad = False
                if contains_harmful_words(user_text):
                    is_bad = True
                else:
                    if ASI_ONE_API_KEY:
                        is_bad = await classify_with_asione(user_text)
                    elif GEMINI_API_KEY and genai:
                        is_bad = await classify_with_gemini(user_text)
                    else:
                        is_bad = False
                reply = f"Inappropriate: {'YES' if is_bad else 'NO'}"
            except Exception as e:
                ctx.logger.error(f"Chat moderation error: {e}")
                reply = "Sorry, I couldn't process that right now."

        await ctx.send(sender, ChatMessage(
            timestamp=datetime.utcnow(),
            msg_id=uuid4(),
            content=[
                TextContent(type="text", text=reply),
                EndSessionContent(type="end-session")
            ],
        ))

    agent.include(moderation_protocol)
    agent.include(chat_proto,publish_manifest=True)

    return agent



# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------
def main():
    if not MODERATOR_AGENT_SEED:
        raise ValueError("MODERATOR_AGENT_SEED environment variable not set. Please set it in .env")
    agent = create_moderator_agent(seed=MODERATOR_AGENT_SEED)
    print("Starting moderator agent... (listening on port 8000)")
    agent.run()


if __name__ == "__main__":
    main()
