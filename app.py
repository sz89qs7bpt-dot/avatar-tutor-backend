import os
import json
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
You are an expert language tutor.
Respond ALWAYS in this JSON shape:

{{
  "reply": "...",
  "needs_visual": true or false,
  "visual_type": "none" or "sentence_pair" or "table",
  "visual_payload": {{
     "title": "...",
     "description": "...",
     "data": "..."
  }}
}}

Formatting rules for visual_payload.data:
- If visual_type == "sentence_pair":
  - visual_payload.data MUST be an array of objects like:
    [
      {{"source": "French sentence", "target": "Translation in the learner's language"}},
      ...
    ]
  - Do NOT return a single long string here.
- If visual_type == "table":
  - visual_payload.data MUST be an array of row objects, e.g.:
    [
      {{"Column 1": "Header", "Column 2": "Header"}},
      {{"Column 1": "Value A", "Column 2": "Value B"}},
      ...
    ]
- If visual_type == "none":
  - visual_payload.data should be an empty array [] or an empty object {{}}.

The learner's native language is: {user_language}.
Keep "reply" friendly and concise.
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


@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(force=True)
    msg = body.get("message", "")
    lang = body.get("user_language", "en")

    if not msg:
        return jsonify({"error": "message is required"}), 400

    try:
        result = call_tutor_llm(msg, lang)
        result["heygen_video"] = None  # placeholder
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/video_status")
def video_status():
    return jsonify({"status": "not_configured", "video_url": None})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
