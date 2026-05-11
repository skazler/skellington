"""Report formatting skill for Mayor."""

from __future__ import annotations


async def format_reports(data: str, output_format: str = "markdown") -> str:
    """
    Convert data to different output formats.

    Args:
        data: Data to format
        output_format: Target format ("markdown", "json", "csv", "html")

    Returns:
        Formatted data
    """
    try:
        import csv
        import io
        import json

        # Try to parse input data
        try:
            parsed_data = json.loads(data)
        except json.JSONDecodeError:
            # Assume it's text data, try to structure it
            parsed_data = {"content": data}

        if output_format == "json":
            return json.dumps(parsed_data, indent=2)

        elif output_format == "markdown":
            if isinstance(parsed_data, dict):
                md = "# Formatted Report\n\n"
                for key, value in parsed_data.items():
                    if isinstance(value, (list, dict)):
                        md += f"## {key.title()}\n\n"
                        if isinstance(value, list):
                            for item in value:
                                md += f"- {item}\n"
                        else:
                            for k, v in value.items():
                                md += f"- **{k}**: {v}\n"
                    else:
                        md += f"## {key.title()}\n\n{value}\n\n"
                return md
            else:
                return f"# Report\n\n{parsed_data}"

        elif output_format == "csv":
            if isinstance(parsed_data, list) and parsed_data and isinstance(parsed_data[0], dict):
                # List of dictionaries
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=parsed_data[0].keys())
                writer.writeheader()
                writer.writerows(parsed_data)
                return output.getvalue()
            elif isinstance(parsed_data, dict):
                # Single dictionary
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["Key", "Value"])
                for key, value in parsed_data.items():
                    writer.writerow([key, str(value)])
                return output.getvalue()
            else:
                return f"Key,Value\\nContent,{parsed_data}"

        elif output_format == "html":
            html = "<!DOCTYPE html><html><head><title>Report</title></head><body>"
            html += "<h1>Formatted Report</h1>"

            if isinstance(parsed_data, dict):
                for key, value in parsed_data.items():
                    html += f"<h2>{key.title()}</h2>"
                    if isinstance(value, list):
                        html += "<ul>"
                        for item in value:
                            html += f"<li>{item}</li>"
                        html += "</ul>"
                    else:
                        html += f"<p>{value}</p>"
            else:
                html += f"<p>{parsed_data}</p>"

            html += "</body></html>"
            return html

        else:
            return (
                f"❓ Unsupported format: {output_format}. Try 'markdown', 'json', 'csv', or 'html'."
            )

    except Exception as e:
        return f"Error formatting report: {str(e)}"


SCHEMA = {
    "type": "object",
    "properties": {
        "data": {
            "type": "string",
            "description": "Structured data (JSON string or unstructured text) to convert to the specified output format",
        },
        "output_format": {
            "type": "string",
            "enum": ["markdown", "json", "csv", "html"],
            "description": "Target output format (markdown for docs, json for APIs, csv for spreadsheets, html for web)",
            "default": "markdown",
        },
    },
    "required": ["data"],
}
