"""Web search skill for Oogie."""

from __future__ import annotations


async def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web for information on a given query.

    Args:
        query: The search query
        max_results: Maximum number of results to return

    Returns:
        Formatted search results
    """
    try:
        from skellington.subagents.search import SearchSubagent

        # Use the search subagent
        search_agent = SearchSubagent()
        results = await search_agent.run(query)

        # Format results
        formatted_results = []
        for i, result in enumerate(results.results[:max_results], 1):
            formatted_results.append(f"""
{i}. **{result.title}**
   URL: {result.url}
   Summary: {result.snippet}
   Relevance: {result.relevance_score:.2f}
""")

        report = f"🔍 Web Search Results for: '{query}'\\n"
        report += f"Found {len(results.results)} results, showing top {min(max_results, len(results.results))}\\n\\n"
        report += "".join(formatted_results)

        return report

    except Exception as e:
        return f"Error performing web search: {str(e)}"


SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Search query string to look up on the web (e.g., 'Python async libraries 2024')",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of search results to return",
            "default": 5,
            "minimum": 1,
            "maximum": 20,
        },
    },
    "required": ["query"],
}
