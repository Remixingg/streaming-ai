import os
import google.generativeai as genai
import httpx
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
async_client = httpx.AsyncClient()
# if not OPENAI_API_KEY:
#     raise ValueError("Not found: OPENAI_API_KEY")


async def query_gemini_moderator(text_to_check: str) -> bool:
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not configured.")
        return False

    model = genai.GenerativeModel('gemini-1.5-flash-latest')

    prompt = (
        "You are a thoughtful, context-aware moderator for a fun, energetic live streaming platform. "
        "Your goal is to protect the community from truly harmful content while allowing for playful banter and jokes. "
        "You must classify the user's message into one of two categories:\n\n"
        "1. **Playful Banter / Mild Trash Talk (Acceptable):** This includes things like 'noob', 'L', 'get rekt', 'you're so bad at this game lol', 'dummy', 'stupid play'. These are generally acceptable in a gaming context.\n\n"
        "2. **Truly Harmful Content (Unacceptable):** This includes slurs (e.g., the r-slur, the aut-slur, etc.), harassment, severe personal attacks, encouraging self-harm, racist or sexist remarks, and explicit sexual language. This is never acceptable.\n\n"
        "Now, analyze the following user message. Based on these definitions, is the message **Truly Harmful**? "
        "Respond with only one word: 'YES' if it is Truly Harmful, or 'NO' if it is not."
    )
    full_prompt = f"{prompt}\n\nUSER MESSAGE: '{text_to_check}'"

    try:
        response = await model.generate_content_async(full_prompt)
        answer = response.text.strip().upper()

        print(f"Text: '{text_to_check}' | Gemini Async Response: '{answer}'")
        return answer == "YES"

    except Exception as e:
        print(f"An error occurred while querying Gemini: {e}")
        return False


def query_openai_moderator(text_to_check: str) -> bool:
    try:
        system_prompt = (
            "You are a thoughtful, context-aware moderator for a fun, energetic live streaming platform. "
            "Your goal is to protect the community from truly harmful content while allowing for playful banter and jokes. "
            "You must classify the user's message into one of two categories:\n\n"
            "1. **Playful Banter / Mild Trash Talk (Acceptable):** This includes things like 'noob', 'L', 'get rekt', 'you're so bad at this game lol', 'dummy', 'stupid play'. These are generally acceptable in a gaming context.\n\n"
            "2. **Truly Harmful Content (Unacceptable):** This includes slurs (e.g., the r-slur, the aut-slur, etc.), harassment, severe personal attacks, encouraging self-harm, racist or sexist remarks, and explicit sexual language. This is never acceptable.\n\n"
            "Now, analyze the following user message. Based on these definitions, is the message **Truly Harmful**? "
            "Respond with only one word: 'YES' if it is Truly Harmful, or 'NO' if it is not."
        )
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_to_check}
            ],
        )
        answer = response.choices[0].message['content'].strip().upper()
        print(f"Text: '{text_to_check}' | OpenAI response: '{answer}'")
        return answer == "YES"
    except Exception as e:
        print(f"Error querying OpenAI: {e}")
        return False
