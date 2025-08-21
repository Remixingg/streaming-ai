import os
import whisper
import ffmpeg
import requests
import traceback
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv
from uagents import Agent, Context, Protocol, Model
from uagents_core.contrib.protocols.chat import(
    ChatMessage, ChatAcknowledgement, TextContent, chat_protocol_spec
)
from uagents.setup import fund_agent_if_low
from google.generativeai import configure, GenerativeModel
from uuid import uuid4
from supabase import create_client, Client

load_dotenv()



# -------------------------------------------------------------------------
# Config
# -------------------------------------------------------------------------
class Config:
    def __init__(self):
        self.HIGHLIGHT_AGENT_SEED = os.getenv("HIGHLIGHT_AGENT_SEED")
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.SUPABASE_URL= os.getenv("SUPABASE_URL")
        self.SUPABASE_KEY = os.getenv("SUPABASE_KEY")
        self.SUPABASE_BUCKET_HIGHLIGHT_NAME = os.getenv("SUPABASE_BUCKET_HIGHLIGHT_NAME")
        os.environ["PATH"] += os.pathsep + r'C:\ffmpeg'
        self.FFMPEG_PATH = r'C:\ffmpeg\ffmpeg.exe'
        
    def validate(self):
        if not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")
        
config = Config()
config.validate()
configure(api_key=os.getenv('GEMINI_API_KEY'))
gemini_model = GenerativeModel('gemini-2.0-flash')
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)



# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class HighlightRequest(Model):
    video_url: str

class HighlightResponse(Model):
    clips: List[Dict[str, str]]



# -------------------------------------------------------------------------
# Class & Function
# -------------------------------------------------------------------------
class VideoProcessor:

    def __init__(self, clips_folder='clips'):
        self.clips_folder = os.path.abspath(clips_folder)
        os.makedirs(self.clips_folder, exist_ok=True)
        
        try:
            self.transcription_model = whisper.load_model(name="base", device="cpu")
        except Exception as e:
            raise Exception(f"Failed to load Whisper model: {e}")
        
    def download_video(self, video_url, downloads_folder='downloads'):
        downloads_folder = os.path.abspath(downloads_folder)
        os.makedirs(downloads_folder, exist_ok=True)
        
        video_filename = os.path.basename(video_url)
        video_filename_with_timestamp = f"{video_filename.rsplit('.', 1)[0]}_{datetime.now().timestamp():.0f}.{video_filename.rsplit('.', 1)[1]}"
        
        video_path = os.path.join(downloads_folder, video_filename_with_timestamp)
        response = requests.get(video_url, stream=True)
        if response.status_code == 200:
            with open(video_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(chunk)
            return video_path
        else:
            raise Exception(f"Failed to download video. Status code: {response.status_code}")
    
    def transcribe_video(self, video_path):
        print("Transcribing video...")
        result = self.transcription_model.transcribe(video_path)
        return result['text']
    
    def analyze_highlights(self, transcript):
        print("Analyzing highlights...")
        prompt = f"""Analyze this video transcript and identify the 5 most highlight-worthy moments. 
        For each highlight, provide an exact timestamp in [MM:SS] format and a brief, engaging description.
        Transcript: {transcript}"""
        
        response = gemini_model.generate_content(prompt)
        highlights = self.parse_gemini_response(response.text)
        return highlights
    
    def parse_gemini_response(self, response_text):
        highlights = []
        lines = [line.strip() for line in response_text.split('\n') if line.strip()]
        
        for line in lines:
            if ']' in line and '[' in line:

                time_part = line[line.find('[')+1:line.find(']')]
                description = line[line.find(']')+1:].strip()
                
                mins, secs = map(float, time_part.split(':'))
                start_time = mins * 60 + secs
                end_time = start_time + 30
                # end_time = min(start_time + 5, start_time + 30)
                
                highlights.append({
                    'start': start_time,  
                    'end': end_time,  
                    'description': description
                })
        return highlights[:5]

    def generate_clips(self, video_path, highlights, video_filename):
        print("Generating clips...")
        clips = []
        for i, highlight in enumerate(highlights, 1):
            start = float(highlight['start'])
            duration = float(highlight['end'] - highlight['start'])
            if duration <= 0:
                continue
            clip_filename = f"{video_filename.rsplit('.', 1)[0]}_clip_{i}_{datetime.now().timestamp():.0f}.mp4"
            clip_path = os.path.join(self.clips_folder, clip_filename)
            ffmpeg.input(video_path, ss=start, t=duration).output(clip_path, vcodec='libx264', preset='fast').run(cmd=config.FFMPEG_PATH, quiet=True)
            clips.append({
                'path': clip_path,
                'start': highlight['start'],
                'end': highlight['end'],
                'description': highlight['description']
            })
            subtitle_text = highlight.get('subtitle', highlight['description'])
            subtitle_file_path = os.path.join(self.clips_folder, f"{video_filename.rsplit('.', 1)[0]}_clip_{i}_{datetime.now().timestamp():.0f}.txt")
            
            with open(subtitle_file_path, 'w') as subtitle_file:
                subtitle_file.write(subtitle_text)
        return clips

async def upload_clip_to_supabase(clip_path):
    try:
        with open(clip_path, "rb") as file:
            file_name = os.path.basename(clip_path)
            response = supabase.storage.from_(config.SUPABASE_BUCKET_HIGHLIGHT_NAME).upload(file_name, file)

        if response.path:
            url = supabase.storage.from_(config.SUPABASE_BUCKET_HIGHLIGHT_NAME).get_public_url(response.path)
            return url
        else:
            print(f"Failed to upload {clip_path}: No path in response.")
            return None
    except Exception as e:
        print(f"Error uploading clip {clip_path}: {e}")
        return None

async def handle_highlight_generate(video_url, is_chat=False):
    response = HighlightResponse(clips=[])
    if video_url:
        processor = VideoProcessor()
        video_path = processor.download_video(video_url)
        transcript = processor.transcribe_video(video_path)
        highlights = processor.analyze_highlights(transcript)
        clips = processor.generate_clips(video_path, highlights, os.path.basename(video_path))

        if is_chat == True:
            formatted_clips=[]
            for clip in clips:
                clip_url = await upload_clip_to_supabase(clip['path'])
                if clip_url:
                    clip['path'] = clip_url
                if is_chat == True:
                    formatted_clips.append(
                        f"Clip {len(formatted_clips) + 1}:\n\n"
                        f"Description: {clip['description']}\n\n"
                        f"Start Time: {clip['start']}s\n\n"
                        f"End Time: {clip['end']}s\n\n"
                        f"[Download Clip]({clip['path']})\n\n"
                        "--------------------\n\n"
                    )
            response.clips=formatted_clips
        else:
            for clip in clips:
                clip_url = await upload_clip_to_supabase(clip['path'])
                if clip_url:
                    clip['path'] = clip_url
            response.clips=clips

    return response

async def is_valid_video_url(video_url: str) -> bool:
    try:
        response = requests.head(video_url, allow_redirects=True)
        if response.status_code == 200 and "video" in response.headers.get("Content-Type", "").lower():
            return True
    except requests.RequestException:
        pass
    return False    



# -------------------------------------------------------------------------
# Agent Creation
# -------------------------------------------------------------------------
def create_video_processing_agent(seed: str) -> Agent:
    if not seed:
        raise ValueError("Not found/set: HIGHLIGHT_AGENT_SEED")

    agent = Agent(
        name="highlight_agent",
        seed=seed,
        port=8001,
        mailbox=True,
        publish_agent_details=True,
        readme_path="highlight/highlight_README.md",
    )

    try:
        fund_agent_if_low(agent.wallet.address())
    except Exception:
        print("fund_agent_if_low failed or not available in this environment")

    highlight_protocol = Protocol("HighlightProcessing")

    @highlight_protocol.on_message(model=HighlightRequest, replies=HighlightResponse)
    async def handle_video_processing(ctx: Context, sender: str, msg: HighlightRequest):
        video_url = msg.video_url
        ctx.logger.info(f"[highlight] Received highlight request for text: '{video_url}'")
        response = await handle_highlight_generate(video_url)
        await ctx.send(sender, response)

    @agent.on_rest_post("/generate_highlight", HighlightRequest, HighlightResponse)
    async def rest_generate_highlights(ctx: Context, req: HighlightRequest) -> HighlightResponse:
        video_url = req.video_url
        response = await handle_highlight_generate(video_url)
        return response


    chat_proto = Protocol(spec=chat_protocol_spec)

    @chat_proto.on_message(ChatMessage)
    async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
        await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id))

        user_text = None
        for item in msg.content:
            if isinstance(item, TextContent):
                user_text = item.text
                break

        response = await handle_highlight_generate(user_text,is_chat=True)
        await ctx.send(sender, ChatMessage(
            timestamp=datetime.utcnow(),
            msg_id=uuid4(),
            content=[TextContent(type="text", text="\n".join(response.clips))],
        ))

    @chat_proto.on_message(ChatAcknowledgement)
    async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
        ctx.logger.info(
            f"Received chat acknowledgement from {sender} for {msg.acknowledged_msg_id}"
        )

    try:
        agent.include(highlight_protocol)
        agent.include(chat_proto, publish_manifest=True)
    except Exception as e:
        print("Error including protocol:", e)
        traceback.print_exc()

    return agent



# -------------------------------------------------------------------------
# Run
# -------------------------------------------------------------------------
def main():
    agent = create_video_processing_agent(seed=config.HIGHLIGHT_AGENT_SEED)
    print("Starting highlight agent... (listening on port 8001)")
    agent.run()


if __name__ == "__main__":
    main()
