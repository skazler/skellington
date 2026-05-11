"""Visualization skill for Mayor."""

from __future__ import annotations


async def create_visualizations(data: str, chart_type: str = "bar") -> str:
    """
    Create visualizations from data.

    Args:
        data: Data to visualize (JSON, CSV, or structured text)
        chart_type: Type of chart ("bar", "line", "pie", "histogram")

    Returns:
        ASCII art visualization or description
    """
    try:
        import json

        # Try to parse as JSON first
        try:
            parsed_data = json.loads(data)
        except json.JSONDecodeError:
            # Try to parse as simple key-value pairs
            parsed_data = {}
            for line in data.strip().split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    try:
                        parsed_data[key.strip()] = float(value.strip())
                    except ValueError:
                        parsed_data[key.strip()] = value.strip()

        if not isinstance(parsed_data, dict):
            return "❌ Data must be a dictionary/object with numeric values for visualization"

        # Filter to numeric values only
        numeric_data = {k: v for k, v in parsed_data.items() if isinstance(v, (int, float))}

        if not numeric_data:
            return "❌ No numeric data found for visualization"

        if chart_type == "bar":
            # Create ASCII bar chart
            max_value = max(numeric_data.values())
            max_label_len = max(len(str(k)) for k in numeric_data.keys())

            chart = "📊 Bar Chart\n\n"
            for key, value in numeric_data.items():
                bar_length = int((value / max_value) * 20) if max_value > 0 else 0
                bar = "█" * bar_length
                chart += f"{str(key):<{max_label_len}} | {bar} {value}\n"

            return chart

        elif chart_type == "pie":
            # Simple text-based pie chart representation
            total = sum(numeric_data.values())
            chart = "🥧 Pie Chart Breakdown\n\n"

            for key, value in numeric_data.items():
                percentage = (value / total * 100) if total > 0 else 0
                bars = int(percentage / 5)  # 20 bars = 100%
                bar_chart = "█" * bars
                chart += f"{key}: {bar_chart} {percentage:.1f}%\n"

            return chart

        elif chart_type == "line":
            # Simple line chart
            values = list(numeric_data.values())
            labels = list(numeric_data.keys())

            chart = "📈 Line Chart\n\n"
            max_val = max(values) if values else 0
            min_val = min(values) if values else 0
            range_val = max_val - min_val if max_val != min_val else 1

            for i, (label, value) in enumerate(zip(labels, values)):
                # Normalize to 0-10 scale
                normalized = int(((value - min_val) / range_val) * 10) if range_val > 0 else 0
                line = " " * normalized + "●"
                chart += f"{label}: {line} {value}\n"

            return chart

        else:
            return f"❓ Unsupported chart type: {chart_type}. Try 'bar', 'pie', or 'line'."

    except Exception as e:
        return f"Error creating visualization: {str(e)}"


SCHEMA = {
    "type": "object",
    "properties": {
        "data": {
            "type": "string",
            "description": "Numeric data to visualize as ASCII art (JSON object or key:value pairs, must contain numeric values)",
        },
        "chart_type": {
            "type": "string",
            "enum": ["bar", "line", "pie", "histogram"],
            "description": "Type of ASCII chart to generate (bar for comparisons, line for trends, pie for distribution)",
            "default": "bar",
        },
    },
    "required": ["data"],
}
