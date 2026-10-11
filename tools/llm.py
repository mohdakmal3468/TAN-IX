"""
tools/llm.py
------------
One place that calls Gemini. Uses Google Cloud Project ID (Vertex AI) with the `google-genai` SDK.
"""
import os

MODEL_NAME = os.getenv("GEMINI_MODEL", os.getenv("VERTEX_MODEL", "gemini-3.1-flash"))


def get_genai_client():
    """Initializes and returns a Google GenAI Client using Vertex AI with Project ID."""
    from google import genai

    project_id = (
        os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCP_PROJECT_ID")
        or os.getenv("PROJECT_ID")
    )
    location = os.getenv("GOOGLE_CLOUD_LOCATION", os.getenv("GCP_LOCATION", "us-central1"))

    if project_id and project_id not in ("your_gcp_project_id", "your_project_id", ""):
        return genai.Client(vertexai=True, project=project_id, location=location)
    
    # Fallback to standard client (will pick up ADC or environment variables)
    return genai.Client()


def ask_gemini(prompt: str) -> str:
    """Sends prompt to Gemini model using the google-genai SDK. Returns response text."""
    try:
        client = get_genai_client()
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        text = (response.text or "").strip()
        if text:
            return text
        return ""
    except Exception as e:
        return f"Exception: Failed to get response from Gemini - {str(e)}"