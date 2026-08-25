from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_experiment_comparison(
    experiment_summaries: list[dict[str, Any]],
    *,
    comparison_path: Path,
    plots_path: Path,
) -> None:
    rows = _comparison_rows(experiment_summaries)
    comparison_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_path.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_experiment_plots(rows, plots_path)


def _comparison_rows(experiment_summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for experiment in experiment_summaries:
        summary = experiment["summary"]
        rows.append(
            {
                "id": experiment["id"],
                "description": experiment.get("description", ""),
                "runs": experiment.get("runs", summary.get("runs", 1)),
                "success_rate": summary["success_rate"],
                "passed": summary["passed"],
                "failed": summary["failed"],
                "total": summary["total"],
                "avg_tool_calls": summary["avg_tool_calls"],
                "avg_duration_seconds": summary["avg_duration_seconds"],
                "input_tokens": summary["input_tokens"],
                "output_tokens": summary["output_tokens"],
                "total_tokens": summary["input_tokens"] + summary["output_tokens"],
                "use_structured_memory": experiment.get("use_structured_memory", False),
                "error_categories": summary.get("error_categories", {}),
                "by_difficulty": summary.get("by_difficulty", {}),
            }
        )
    return rows


def _xml_escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _bar_plot_svg(
    *,
    title: str,
    labels: list[str],
    values: list[float],
    x: int,
    y: int,
    width: int,
    height: int,
    color: str,
    suffix: str = "",
    lower_is_better: bool = False,
) -> list[str]:
    max_value = max(values) if values else 0
    scale_max = max(max_value, 1)
    chart_x = x + 52
    chart_y = y + 42
    chart_w = width - 82
    chart_h = height - 92
    bar_gap = 12
    bar_w = max(14, int((chart_w - bar_gap * max(len(values) - 1, 0)) / max(len(values), 1)))

    lines = [
        f'<text x="{x}" y="{y + 20}" class="title">{_xml_escape(title)}</text>',
        f'<line x1="{chart_x}" y1="{chart_y + chart_h}" x2="{chart_x + chart_w}" y2="{chart_y + chart_h}" class="axis" />',
        f'<line x1="{chart_x}" y1="{chart_y}" x2="{chart_x}" y2="{chart_y + chart_h}" class="axis" />',
    ]
    hint = "menor es mejor" if lower_is_better else "mayor es mejor"
    lines.append(f'<text x="{x + width - 96}" y="{y + 20}" class="hint">{hint}</text>')

    for index, (label, value) in enumerate(zip(labels, values)):
        bar_h = int((value / scale_max) * chart_h) if scale_max else 0
        bx = chart_x + index * (bar_w + bar_gap)
        by = chart_y + chart_h - bar_h
        lines.extend(
            [
                f'<rect x="{bx}" y="{by}" width="{bar_w}" height="{bar_h}" rx="3" fill="{color}" />',
                f'<text x="{bx + bar_w / 2:.1f}" y="{by - 7}" class="value" text-anchor="middle">{value:g}{suffix}</text>',
                f'<text x="{bx + bar_w / 2:.1f}" y="{chart_y + chart_h + 22}" class="label" text-anchor="middle">{_xml_escape(label)}</text>',
            ]
        )
    return lines


def _stacked_error_plot_svg(
    *,
    rows: list[dict[str, Any]],
    x: int,
    y: int,
    width: int,
    height: int,
) -> list[str]:
    labels = [row["id"] for row in rows]
    all_categories: dict[str, int] = {}
    for row in rows:
        for category, count in row["error_categories"].items():
            all_categories[category] = all_categories.get(category, 0) + int(count)
    categories = [
        category
        for category, _ in sorted(all_categories.items(), key=lambda item: item[1], reverse=True)[:5]
    ]
    colors = ["#ef4444", "#f97316", "#eab308", "#8b5cf6", "#64748b"]
    totals = [
        sum(int(row["error_categories"].get(category, 0)) for category in categories)
        for row in rows
    ]
    scale_max = max(max(totals) if totals else 1, 1)
    chart_x = x + 52
    chart_y = y + 42
    chart_w = width - 82
    chart_h = height - 104
    bar_gap = 12
    bar_w = max(14, int((chart_w - bar_gap * max(len(rows) - 1, 0)) / max(len(rows), 1)))

    lines = [
        f'<text x="{x}" y="{y + 20}" class="title">Errores por categoria</text>',
        f'<text x="{x + width - 96}" y="{y + 20}" class="hint">menor es mejor</text>',
        f'<line x1="{chart_x}" y1="{chart_y + chart_h}" x2="{chart_x + chart_w}" y2="{chart_y + chart_h}" class="axis" />',
        f'<line x1="{chart_x}" y1="{chart_y}" x2="{chart_x}" y2="{chart_y + chart_h}" class="axis" />',
    ]

    for row_index, row in enumerate(rows):
        bx = chart_x + row_index * (bar_w + bar_gap)
        current_y = chart_y + chart_h
        total = 0
        for category_index, category in enumerate(categories):
            value = int(row["error_categories"].get(category, 0))
            total += value
            segment_h = int((value / scale_max) * chart_h)
            current_y -= segment_h
            lines.append(
                f'<rect x="{bx}" y="{current_y}" width="{bar_w}" height="{segment_h}" rx="2" fill="{colors[category_index]}" />'
            )
        label_y = chart_y + chart_h - int((total / scale_max) * chart_h) - 7
        lines.extend(
            [
                f'<text x="{bx + bar_w / 2:.1f}" y="{label_y}" class="value" text-anchor="middle">{total:g}</text>',
                f'<text x="{bx + bar_w / 2:.1f}" y="{chart_y + chart_h + 22}" class="label" text-anchor="middle">{_xml_escape(labels[row_index])}</text>',
            ]
        )

    legend_x = x + 18
    legend_y = y + height - 30
    for index, category in enumerate(categories):
        lx = legend_x + index * 126
        lines.extend(
            [
                f'<rect x="{lx}" y="{legend_y}" width="10" height="10" fill="{colors[index]}" />',
                f'<text x="{lx + 15}" y="{legend_y + 9}" class="legend">{_xml_escape(category)}</text>',
            ]
        )
    if not categories:
        lines.append(f'<text x="{chart_x + 12}" y="{chart_y + 40}" class="empty">Sin errores clasificados</text>')
    return lines


def _write_experiment_plots(rows: list[dict[str, Any]], path: Path) -> None:
    labels = [row["id"] for row in rows]
    success_values = [round(float(row["success_rate"]) * 100, 1) for row in rows]
    tool_values = [float(row["avg_tool_calls"]) for row in rows]
    token_values = [float(row["total_tokens"]) for row in rows]

    width = 1280
    height = 840
    panel_w = 570
    panel_h = 320
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text{font-family:Arial,Helvetica,sans-serif;fill:#172033}",
        ".page-title{font-size:26px;font-weight:700}",
        ".page-subtitle{font-size:14px;fill:#64748b}",
        ".panel{fill:#ffffff;stroke:#d7dee8;stroke-width:1}",
        ".title{font-size:18px;font-weight:700}",
        ".hint,.legend{font-size:11px;fill:#64748b}",
        ".axis{stroke:#94a3b8;stroke-width:1}",
        ".value{font-size:12px;font-weight:700}",
        ".label{font-size:10px;fill:#334155}",
        ".empty{font-size:14px;fill:#64748b}",
        "</style>",
        '<rect x="0" y="0" width="1280" height="840" fill="#f8fafc" />',
        '<text x="42" y="45" class="page-title">Comparacion de experimentos M3</text>',
        '<text x="42" y="70" class="page-subtitle">Metricas principales para elegir la variante mas robusta y eficiente.</text>',
    ]
    for px, py in [(40, 100), (670, 100), (40, 480), (670, 480)]:
        svg.append(f'<rect x="{px}" y="{py}" width="{panel_w}" height="{panel_h}" rx="8" class="panel" />')

    svg.extend(
        _bar_plot_svg(
            title="Tasa de exito",
            labels=labels,
            values=success_values,
            x=66,
            y=124,
            width=panel_w - 52,
            height=panel_h - 42,
            color="#16a34a",
            suffix="%",
        )
    )
    svg.extend(
        _bar_plot_svg(
            title="Promedio de tool calls",
            labels=labels,
            values=tool_values,
            x=696,
            y=124,
            width=panel_w - 52,
            height=panel_h - 42,
            color="#2563eb",
            lower_is_better=True,
        )
    )
    svg.extend(
        _bar_plot_svg(
            title="Tokens totales",
            labels=labels,
            values=token_values,
            x=66,
            y=504,
            width=panel_w - 52,
            height=panel_h - 42,
            color="#0f766e",
            lower_is_better=True,
        )
    )
    svg.extend(
        _stacked_error_plot_svg(
            rows=rows,
            x=696,
            y=504,
            width=panel_w - 52,
            height=panel_h - 42,
        )
    )
    svg.append("</svg>")
    path.write_text("\n".join(svg), encoding="utf-8")
