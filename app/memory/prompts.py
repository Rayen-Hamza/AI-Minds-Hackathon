"""
Prompt templates for memory extraction and context packing.
Inspired by Memobase prompts.
"""

from datetime import datetime


# ============================================================================
# Profile Extraction Prompt
# ============================================================================

EXTRACT_PROFILE_SYSTEM = """You are a professional psychologist and conversation analyst.
Your responsibility is to carefully read conversation snippets and extract important user profiles in structured JSON format.
Extract relevant and important facts and preferences about the user that will help understand the user's state.
You will not only extract information that's explicitly stated, but also infer what's implied from the conversation."""

EXTRACT_PROFILE_PROMPT = """Given this conversation snippet, extract any user facts as JSON with two keys:
- "properties": {{ key: value }} — factual attributes (name, role, location, expertise_level, etc.)
- "preferences": {{ key: value }} — likes, dislikes, style preferences, interests, communication_style, etc.

Guidelines:
1. Only extract attributes with actual values from the conversation
2. Infer implied information when reasonable
3. Use specific dates when mentioned, never use relative dates like "today" or "yesterday"
4. For list-valued keys (e.g., interests), provide as arrays
5. Keep values concise and accurate
6. If nothing extractable, return empty objects

Examples:

<example>
<conversation>
User: Hi, I'm working on a Python project
Assistant: Great! What kind of project are you building?
</conversation>
<output>
{{
  "properties": {{
    "expertise_level": "developer"
  }},
  "preferences": {{
    "favorite_language": "Python"
  }}
}}
</output>
</example>

<example>
<conversation>
User: I prefer concise answers, I don't like long explanations
Assistant: Understood, I'll keep my responses brief.
</conversation>
<output>
{{
  "properties": {{}},
  "preferences": {{
    "communication_style": "concise",
    "dislikes": ["long explanations"]
  }}
}}
</output>
</example>

<example>
<conversation>
User: Hey
Assistant: Hello! How can I help you today?
</conversation>
<output>
{{
  "properties": {{}},
  "preferences": {{}}
}}
</output>
</example>

Now extract facts from the following conversation:

<conversation>
{conversation}
</conversation>

Return ONLY valid JSON with "properties" and "preferences" keys. No additional text."""


# ============================================================================
# Context Packing Prompt
# ============================================================================


def pack_context(profile_data: dict, events: list[dict], max_events: int = 5) -> str:
    """
    Pack profile and relevant events into a context string.

    Args:
        profile_data: Dictionary with 'properties' and 'preferences' keys
        events: List of relevant events with 'text' and 'timestamp' keys
        max_events: Maximum number of events to include

    Returns:
        Formatted context string for injection into system prompt
    """
    context_parts = []

    # Add profile section
    if profile_data and (profile_data.get("properties") or profile_data.get("preferences")):
        context_parts.append("# Memory")
        context_parts.append(
            "Unless the user has relevant queries, do not actively mention these memories in the conversation."
        )
        context_parts.append("")
        context_parts.append("## User Profile:")

        properties = profile_data.get("properties", {})
        if properties:
            context_parts.append("**Properties:**")
            for key, value in properties.items():
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                context_parts.append(f"  - {key}: {value}")

        preferences = profile_data.get("preferences", {})
        if preferences:
            context_parts.append("**Preferences:**")
            for key, value in preferences.items():
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                context_parts.append(f"  - {key}: {value}")

    # Add events section
    if events:
        if context_parts:
            context_parts.append("")
        context_parts.append("## Relevant Past Context:")

        # Limit to max_events, prioritize most recent
        limited_events = events[-max_events:] if len(events) > max_events else events

        for event in limited_events:
            timestamp = event.get("timestamp", "")
            text = event.get("text", "")

            # Format timestamp if it's a datetime object
            if isinstance(timestamp, datetime):
                timestamp = timestamp.strftime("%Y-%m-%d %H:%M")

            if text:
                # Truncate long event text
                if len(text) > 200:
                    text = text[:197] + "..."
                context_parts.append(f"- [{timestamp}] {text}")

    if context_parts:
        context_parts.append("")
        context_parts.append("---")
        return "\n".join(context_parts)

    return ""


# ============================================================================
# Extraction Helper
# ============================================================================


def format_conversation_for_extraction(
    user_message: str, assistant_response: str
) -> str:
    """
    Format a conversation turn for profile extraction.

    Args:
        user_message: The user's message
        assistant_response: The assistant's response

    Returns:
        Formatted conversation string
    """
    return f"""User: {user_message}
Assistant: {assistant_response}"""
