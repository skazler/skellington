"""Research summarization skill for Oogie."""

from __future__ import annotations

import re


async def summarize_findings(content: str, max_length: int = 300) -> str:
    """
    Create a concise summary of research findings or content.

    Args:
        content: The content to summarize
        max_length: Maximum length of summary in words

    Returns:
        Concise summary
    """
    try:
        # Simple extractive summarization
        sentences = re.split(r"[.!?]+", content)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Score sentences by position and length
        scored_sentences = []
        for i, sentence in enumerate(sentences):
            # Prefer sentences in the middle and at the end (conclusion)
            position_score = 1.0
            if i < len(sentences) * 0.2:  # First 20%
                position_score = 0.7
            elif i > len(sentences) * 0.8:  # Last 20%
                position_score = 1.2

            # Prefer longer sentences (likely more informative)
            length_score = min(len(sentence.split()) / 10, 2.0)

            # Prefer sentences with key terms
            key_terms = [
                "important",
                "significant",
                "key",
                "main",
                "conclusion",
                "result",
                "finding",
            ]
            keyword_score = 1.0 + sum(1 for term in key_terms if term in sentence.lower()) * 0.5

            total_score = position_score * length_score * keyword_score
            scored_sentences.append((sentence, total_score))

        # Select top sentences
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        selected_sentences = scored_sentences[:5]  # Top 5 sentences

        # Sort back to original order for coherence
        selected_sentences.sort(key=lambda x: sentences.index(x[0]))

        summary = " ".join([s[0] for s in selected_sentences])

        # Truncate if too long
        words = summary.split()
        if len(words) > max_length:
            summary = " ".join(words[:max_length]) + "..."

        return f"📋 Summary ({len(words)} words):\\n\\n{summary}"

    except Exception as e:
        return f"Error summarizing findings: {str(e)}"


SCHEMA = {
    "type": "object",
    "properties": {
        "content": {
            "type": "string",
            "description": "Research findings or article text to create a concise extractive summary from",
        },
        "max_length": {
            "type": "integer",
            "description": "Maximum length of generated summary in words",
            "default": 300,
            "minimum": 50,
            "maximum": 1000,
        },
    },
    "required": ["content"],
}
