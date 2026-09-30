import os
from google import genai
from google.genai import types
from bot.config import settings

client = genai.Client(api_key=settings.gemini_api_key)

contents = [
    {"role": "user", "parts": [{"text": "hi, I am yoni"}]},
    {"role": "model", "parts": [{"text": "hello yoni!"}]},
    {"role": "user", "parts": [{"text": "what is my name?"}]}
]

resp = client.models.generate_content(
    model='gemini-3.8-flash',
    contents=contents,
)
print(resp.text)
