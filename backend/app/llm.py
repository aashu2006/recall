"""The single LLM client. Every LLM call in the backend goes through here.

Groq is primary, Gemini Flash-Lite is the fallback. Model names come from env
(GROQ_MODEL, GEMINI_MODEL). Responses are JSON.
"""
