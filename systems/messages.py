"""Helpers sur les messages LangChain, partagés par le superviseur et les sous-agents."""


def extract_text(raw_content) -> str:
    """Gemini renvoie soit une chaîne, soit une liste de blocs de contenu."""
    if not isinstance(raw_content, list):
        return str(raw_content)

    text_parts = []
    for block in raw_content:
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(block.get("text", ""))
        elif isinstance(block, str):
            text_parts.append(block)
    return "\n".join(text_parts)
