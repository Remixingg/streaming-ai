# Strevo - AI Agents for a Decentralized Streaming Platform

[![Hackathon Submission](https://img.shields.io/badge/DoraHacks-NextGen%20Agents-blue)](https://dorahacks.io/hackathon/nextgen-agents/buidl)
[![Built with uAgents](https://img.shields.io/badge/Built%20with-uAgents-3D8BD3?logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNOS40MjQ5MyAxOS40MDQ3TDIuMjUgMTIuMjI5N0w5LjQyNDkzIDQuOTk5NjZMMTEuNzQ5OSAyLjY3NDY2TDE2LjA1OCA3LjAyOTY2TDEyLjY3NDkgMTAuNDE0N0wxNC4yNSA5LjM4OTY2TDE4LjYgMTMuNzM5N0wxNC4yNSA4LjE2NDY2TDEwLjUgMTEuOTE0N0wxMi42NzQ5IDE0LjA4OTdMOC45MjQ5MyAxMC4zMzk3TDUuMDk5OTMgMTIuMjI5N0w4LjkyNDkzIDE1LjkxNDdMMTAuNSA4LjE2NDY2TDEyLjY3NDkgMTAuMzM5N0wxNi4wNTggNi45NTQ2NkwxMS43NDk5IDEuMTk5NjZMMi4yNSAxMC42OTQ3TDkuNDI0OTMgMTcuODg5N0wxMS43NDk5IDIwLjIxNDdMMTkuMDQ5OSAxMi45MTQ3TDIxLjcgMTUuNTY0N0wxMS43NDk5IDI1LjYxNDdMOS40MjQ5MyAxOS40MDQ3WiIgZmlsbD0id2hpdGUiLz48L3N2Zz4=)](https://fetch.ai/uagents)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://www.python.org/)

This repository contains the source code for the two Python-based AI agents developed for the Strevo project, a submission to the DoraHacks NextGen Agents Hackathon.

---

## 📑 Table of Contents

- [Introduction: The Vision for Strevo](#-introduction-the-vision-for-strevo)
- [The AI Agents](#-the-ai-agents)
  - [1. Moderator Agent](#1-moderator-agent)
  - [2. Highlight Agent](#2-highlight-agent)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [Getting Started](#-getting-started)
  - [Prerequisites](#1-prerequisites)
  - [Installation](#2-installation)
- [Running the AI Agents](#-running-the-ai-agents)
- [Testing the API Endpoints](#-testing-the-api-endpoints)
  - [Test the Moderator Agent](#test-the-moderator-agent)
  - [Test the Highlight Agent](#test-the-highlight-agent)

---

## 🚀 Introduction: The Vision for Strevo

Traditional streaming platforms like Twitch and YouTube face significant challenges with content moderation, user engagement, and centralization. Weak moderation leads to toxic communities viewers often miss the most exciting moments of a long stream.

**Strevo** was envisioned as a next-generation, decentralized streaming platform built on the Internet Computer Protocol (ICP) that solves these problems using autonomous AI agents. AI for real-time content moderation and automatic highlight generation, Strevo aims to create a safer, more engaging, and more rewarding experience for both creators and viewers.

This repository contains the code for the two core AI agents that power these features.

## 🤖 The AI Agents

The AI functionality is handled by two independent, autonomous agents built with Fetch.ai's `uagents` library.

### 1. Moderator Agent

provides real-time chat moderation to filter harmful and inappropriate content while allowing for playful banter.

* It receives a chat message, classifies it as either "Truly Harmful" or "Acceptable," and returns a boolean response.
* **Methodology:** It uses a powerful system prompt with a Gemini or ASI:One LLM to understand the context of the message, combined with a keyword-based pre-filter for instantly blocking universally unacceptable terms.

![Moderator Agent in Action](moderator/moderator-preview.gif)

### 2. Highlight Agent

This agent automatically creates short, engaging highlight clips from full-length video streams, solving the problem of viewers missing key moments.

* **Function:** It takes a video URL, downloads it, transcribes the audio, analyzes the transcript to find highlight-worthy moments, and generates video clips of those moments.
* **Methodology:**
    1.  **Transcription:** Uses OpenAI's `Whisper` to generate a full text transcript of the video.
    2.  **Analysis:** Prompts a Gemini LLM to analyze the transcript and identify the top 5 most exciting moments, returning timestamps and descriptions.
    3.  **Clipping:** Uses `FFmpeg` to precisely cut the original video at the identified timestamps, creating short highlight clips.
    4.  **Storage:** Uploads the generated clips to a Supabase bucket for easy access.

![Highlight Agent in Action](highlight/highlight-preview.gif)

## 🏗️ System Architecture

Strevo is a multi-component system. This repository contains the **Python AI Layer** only. The frontend and backend are in separate repositories.

The general architecture is as follows:
1.  **Frontend (ReactJS):** The user interacts with the web application.
2.  **Backend (Go/ExpressJS):** The backend server handles business logic and communicates with the AI agents via HTTP requests to their REST APIs.
3.  **AI Layer (Python/uAgents):** The two agents run as independent microservices, exposing endpoints to handle moderation and highlight generation requests.

## 🛠️ Tech Stack

The technologies used specifically for these AI agents include:

* **Core:** Python 3.9+
* **AI Agents:** Fetch.ai `uagents`
* **LLMs:** Google Gemini, ASI:One
* **Transcription:** OpenAI Whisper
* **Video Processing:** FFmpeg
* **Cloud Storage:** Supabase
* **NLP:** A custom pipeline for classification and analysis

---

## 🚀 Getting Started

Follow these instructions to set up and run the AI agents on your local machine.

### 1. Prerequisites

* **Python:** Ensure you have Python 3.9 or newer installed.
* **FFmpeg:** This is a critical system-level dependency that must be installed manually.
    * **macOS:** `brew install ffmpeg`
    * **Ubuntu/Debian:** `sudo apt-get install ffmpeg`
    * **Windows:** Download from the [official site](https://ffmpeg.org/download.html) and add the `bin` directory to your system's PATH.
* **Git:** You will need Git to clone the repository.

### 2. Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Remixingg/streaming-ai.git
    cd streaming-ai
    ```

2.  **Create an Environment File:**
    Create a file named `.env` in the root of the project and populate it with your API keys and configuration. Use the `.env.example` file as a template:
    ```env
    GEMINI_API_KEY=
    MODERATOR_AGENT_SEED=
    HIGHLIGHT_AGENT_SEED=
    ASI_ONE_API_KEY=
    ASI_ONE_URL=
    ASI_ONE_MODEL=
    SUPABASE_URL=
    SUPABASE_KEY=
    SUPABASE_BUCKET_HIGHLIGHT_NAME=
    FFMPEG_DIR_PATH=
    FFMPEG_PATH=
    ```

3.  **Install Dependencies for Each Agent:**
    It is highly recommended to use a Python virtual environment.
    ```bash
    # Install dependencies for the moderator agent
    pip install -r moderator_agent/requirements.txt

    # Install dependencies for the highlight agent
    pip install -r highlight_agent/requirements.txt
    ```

## 🏃 Running the AI Agents

The agents are designed to run as separate, concurrent processes. Open two terminal windows.

**In Terminal 1, start the Moderator Agent:**
```bash
python moderator_agent/moderator_agent.py
```
You should see output indicating it is running, likely on port 8002.

**In Terminal 2, start the Highlight Agent:**
```bash
python highlight_agent/highlight_agent.py
```
You should see output indicating it is running, likely on port 8001.

## 🧪 Testing the API Endpoints

You can test the running agents using a tool like `curl` or Postman.

### Test the Moderator Agent

Send a POST request to the `/moderate` endpoint:
```bash
curl -X POST http://localhost:8002/moderate \
-H "Content-Type: application/json" \
-d '{"text": "You are so bad at this game lol"}'
```

### Test the Highlight Agent

Send a POST request to the `/generate_highlight` endpoint with a direct video URL:
```bash
curl -X POST http://localhost:8001/generate_highlight \
-H "Content-Type: application/json" \
-d '{"video_url": "[https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4](https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4)"}'
```
