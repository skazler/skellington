"""Trend analysis skill for Oogie."""

from __future__ import annotations

import re


async def analyze_trends(data: str, data_type: str = "text") -> str:
    """
    Analyze trends and patterns in data or code.

    Args:
        data: The data to analyze (text, code, or structured data)
        data_type: Type of data ("text", "code", "json", "csv")

    Returns:
        Trend analysis report
    """
    try:
        analysis = []

        if data_type == "code":
            # Analyze code patterns
            # Count common patterns
            functions = len(re.findall(r"def \w+", data))
            classes = len(re.findall(r"class \w+", data))
            imports = len(re.findall(r"^(import|from)", data, re.MULTILINE))
            comments = len(re.findall(r"#.*", data))

            analysis.append(f"📊 Code Analysis:")
            analysis.append(f"- Functions: {functions}")
            analysis.append(f"- Classes: {classes}")
            analysis.append(f"- Imports: {imports}")
            analysis.append(f"- Comments: {comments}")

            # Calculate ratios
            total_lines = len(data.split("\\n"))
            code_density = (total_lines - comments) / total_lines if total_lines > 0 else 0
            analysis.append(f"- Code density: {code_density:.2f} (lines of code vs comments)")

            # Identify patterns
            if functions > classes * 2:
                analysis.append("⚡ Pattern: Function-heavy codebase (procedural style)")
            elif classes > functions:
                analysis.append("🏗️ Pattern: Class-heavy codebase (OOP style)")

            if imports > 10:
                analysis.append("📦 Pattern: Heavy external dependencies")

        elif data_type == "text":
            # Analyze text patterns
            words = data.split()
            sentences = re.split(r"[.!?]+", data)

            analysis.append(f"📝 Text Analysis:")
            analysis.append(f"- Total words: {len(words)}")
            analysis.append(f"- Total sentences: {len(sentences)}")
            analysis.append(f"- Average words per sentence: {len(words)/len(sentences):.1f}")

            # Find common words
            word_freq = {}
            for word in words:
                word = word.lower().strip(".,!?")
                if len(word) > 3:  # Skip short words
                    word_freq[word] = word_freq.get(word, 0) + 1

            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
            analysis.append(
                f"- Most common words: {', '.join([f'{word}({count})' for word, count in top_words])}"
            )

        elif data_type == "json":
            # Analyze JSON structure
            import json

            parsed = json.loads(data)

            def analyze_json(obj, path=""):
                results = []
                if isinstance(obj, dict):
                    results.append(f"📂 Object at {path}: {len(obj)} keys")
                    for key, value in obj.items():
                        results.extend(analyze_json(value, f"{path}.{key}" if path else key))
                elif isinstance(obj, list):
                    results.append(f"📋 Array at {path}: {len(obj)} items")
                    if obj and len(obj) <= 3:  # Sample small arrays
                        for i, item in enumerate(obj):
                            results.extend(analyze_json(item, f"{path}[{i}]"))
                else:
                    results.append(f"📄 Value at {path}: {type(obj).__name__}")
                return results

            analysis.extend(analyze_json(parsed))

        else:
            analysis.append(f"❓ Unsupported data type: {data_type}")

        return "\\n".join(analysis)

    except Exception as e:
        return f"Error analyzing trends: {str(e)}"


SCHEMA = {
    "type": "object",
    "properties": {
        "data": {
            "type": "string",
            "description": "Raw data to analyze for trends, patterns, and insights (text, code, JSON string, or CSV format)",
        },
        "data_type": {
            "type": "string",
            "enum": ["text", "code", "json", "csv"],
            "description": "Format type of the input data (determines analysis approach)",
            "default": "text",
        },
    },
    "required": ["data"],
}
