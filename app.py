import os
import json
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.after_request
def add_cors_headers(response):
    # Allow your front-end to call this API from another domain
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

@app.route("/")
def index():
    return "Avatar tutor backend is running. Try POST /api/chat."

def call_tutor_llm(user_message: str, user_language: str = "en"):
    system_prompt = f"""
You are an expert, patient language tutor.

Respond ALWAYS in valid JSON using this exact structure:

{{
  "reply": "string – what the tutor says to the learner",
  "needs_visual": true or false,
  "visual_type": "none" or "sentence_pair" or "table",
  "visual_payload": {{
    "title": "short title",
    "description": "short explanation",
    "data": []
  }}
}}

STRICT formatting rules (very important):

- If visual_type == "sentence_pair":
  - visual_payload.data MUST be an array of objects like:
    [
      {{
        "source": "French sentence",
        "target": "Explanation or translation in the learner's language"
      }}
    ]
  - NEVER return a single long string for data.

- If visual_type == "table":
  - visual_payload.data MUST be an array of row objects, for example:
    [
      {{ "Concept": "y", "Meaning": "replaces à + place" }},
      {{ "Concept": "en", "Meaning": "replaces de + noun" }}
    ]

- If visual_type == "none":
  - visual_payload.data MUST be an empty array []

- Keep sentences short and readable.
- Avoid long unbroken lines.
- The learner’s native language is: {user_language}.
"""

    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    )
    return json.loads(completion.choices[0].message.content)

def create_heygen_video(script_text: str):
    heygen_api_key = os.getenv("HEYGEN_API_KEY")
    avatar_id = os.getenv("HEYGEN_AVATAR_ID")
    voice_id = os.getenv("HEYGEN_VOICE_ID")

    if not heygen_api_key or not avatar_id or not voice_id:
        # Missing configuration → skip video generation
        return None

    url = "https://api.heygen.com/v2/video/generate"
    headers = {
        "X-Api-Key": heygen_api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "video_inputs": [
            {
                "character": { "type": "avatar", "avatar_id": avatar_id },
                "voice": { "type": "text", "voice_id": voice_id, "input_text": script_text }
            }
        ],
        "dimension": { "width": 1280, "height": 720 }
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()

@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():

    # Handle CORS preflight request
    if request.method == "OPTIONS":
        return ("", 200)

    body = request.get_json(force=True)
    msg = body.get("message", "")
    lang = body.get("user_language", "en")

    if not msg:
        return jsonify({"error": "message is required"}), 400

    try:
        result = call_tutor_llm(msg, lang)

        # Generate HeyGen video from the tutor reply
        video_resp = create_heygen_video(result.get("reply", ""))

        result["heygen_video"] = video_resp
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/video_status")
def video_status():
    video_id = request.args.get("video_id")
    if not video_id:
        return jsonify({"error": "video_id required"}), 400

    heygen_api_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_api_key:
        return jsonify({"error": "HEYGEN_API_KEY not configured"}), 500

    url = "https://api.heygen.com/v1/video_status.get"
    headers = { "X-Api-Key": heygen_api_key }

    resp = requests.get(url, headers=headers, params={"video_id": video_id}, timeout=30)
    resp.raise_for_status()

    data = resp.json().get("data", {})

    return jsonify({
        "status": data.get("status"),
        "video_url": data.get("video_url"),
        "raw": data
    })
    
