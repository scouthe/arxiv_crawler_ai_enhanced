import json
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle

DEFAULT_BRAND_LOGO_PATH = Path(
    os.environ.get(
        "WECHAT_CHART_BRAND_LOGO_PATH",
        "/home/heheheh/Documents/coding/gongzhonghao/logo/璇玑枢_彩色透明底_带字.png",
    )
)

# =========================
# 字体与绘图基础配置
# =========================
plt.rcParams["figure.dpi"] = 220
plt.rcParams["axes.unicode_minus"] = False

candidate_fonts = [
    "Noto Sans CJK SC",
    "Noto Sans CJK JP",
    "Noto Sans CJK TC",
    "Source Han Sans SC",
    "WenQuanYi Zen Hei",
    "SimHei",
    "Microsoft YaHei",
]
available_fonts = {f.name for f in fm.fontManager.ttflist}
selected_font = next((f for f in candidate_fonts if f in available_fonts), None)
if selected_font is not None:
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [selected_font]
    CH_FONT = fm.FontProperties(family=selected_font)
else:
    CH_FONT = None

# =========================
# 颜色（按 logo 统一）
# =========================
bg_color = "#F5F6F8"
grid_color = "#D7DCE5"
text_color = "#1F2740"
subtle_text = "#667085"
brand_blue = "#1C2F6C"
brand_blue_2 = "#355FC4"
brand_purple = "#8C7CF0"
brand_purple_2 = "#B094F4"
line_color = "#334EA8"
marker_color = "#4D5FD6"
bar_top = np.array([104, 146, 216]) / 255.0
bar_bottom = np.array([162, 98, 182]) / 255.0
title_left_rgb = np.array([28, 47, 108]) / 255.0
title_right_rgb = np.array([176, 142, 244]) / 255.0


@dataclass
class ChartSpec:
    journal_title: str
    main_title: str
    years: list[int | str]
    values: list[float]
    left_lines: list[str]
    right_lines: list[str]
    variant: str = "wechat_235"
    brand_logo_path: Path | None = None

    @classmethod
    def from_config(cls, journal_title: str, data: dict[str, Any]) -> "ChartSpec":
        years = list(data.get("years", []))
        values = [float(v) for v in data.get("values", [])]
        if not years or not values:
            raise ValueError("years/values 不能为空")
        if len(years) != len(values):
            raise ValueError("years 和 values 长度必须一致")

        brand_logo_raw = str(data.get("brand_logo_path", "")).strip()
        brand_logo_path = Path(brand_logo_raw) if brand_logo_raw else None

        return cls(
            journal_title=str(data.get("journal_title", journal_title)).strip() or journal_title,
            main_title=str(data.get("main_title", "")).strip(),
            years=years,
            values=values,
            left_lines=[str(x).strip() for x in data.get("left_lines", []) if str(x).strip()],
            right_lines=[str(x).strip() for x in data.get("right_lines", []) if str(x).strip()],
            variant=str(data.get("variant", "wechat_235")).strip() or "wechat_235",
            brand_logo_path=brand_logo_path,
        )


# =========================
# 通用函数
# =========================
def make_horizontal_gradient(width: int = 1200, c1=None, c2=None):
    if c1 is None:
        c1 = title_left_rgb
    if c2 is None:
        c2 = title_right_rgb
    grad = np.zeros((1, width, 3))
    for i in range(3):
        grad[0, :, i] = np.linspace(c1[i], c2[i], width)
    return grad


def _resolve_brand_logo_path(spec: ChartSpec) -> Path | None:
    if spec.brand_logo_path:
        return spec.brand_logo_path
    if DEFAULT_BRAND_LOGO_PATH.exists():
        return DEFAULT_BRAND_LOGO_PATH
    return None


def draw_logo(fig, box, logo_path: Path | None):
    if logo_path and logo_path.exists():
        ax = fig.add_axes(box)
        ax.set_axis_off()
        img = mpimg.imread(logo_path)
        ax.imshow(img)
        return ax
    return None


def gradient_bar(ax, x, height, width=0.50, bottom=0):
    n = 256
    grad = np.zeros((n, 1, 3))
    for i in range(3):
        grad[:, 0, i] = np.linspace(bar_bottom[i], bar_top[i], n)

    ax.imshow(
        grad,
        extent=[x - width / 2, x + width / 2, bottom, bottom + height],
        origin="lower",
        aspect="auto",
        zorder=2,
    )

    ax.add_patch(
        Rectangle(
            (x - width / 2, bottom),
            width,
            height,
            fill=False,
            edgecolor=(0, 0, 0, 0.04),
            linewidth=0.8,
            zorder=3,
        )
    )


def _compute_ymax(values: list[float]) -> float:
    max_value = max(values)
    if max_value <= 5:
        return round(max_value + 1.0, 1)
    if max_value <= 20:
        return round(max_value * 1.15 + 0.5, 1)
    return round(max_value * 1.12 + 2.0, 1)


def draw_chart(ax, years, values, x_label_size=12, value_fontsize=14):
    ymax = _compute_ymax(values)
    ax.set_facecolor(bg_color)
    ax.set_xlim(-0.5, len(years) - 0.5)
    ax.set_ylim(0, ymax)

    grid_levels = np.linspace(0, ymax, 5)[1:]
    for y in grid_levels:
        ax.axhline(y, color=grid_color, lw=1.0, zorder=0)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color("#3A435E")
    ax.spines["bottom"].set_linewidth(1.0)

    ax.tick_params(axis="y", left=False, labelleft=False)
    ax.tick_params(axis="x", length=0)
    ax.set_xticks(range(len(years)))
    ax.set_xticklabels(years, fontsize=x_label_size, color=text_color)

    for i, v in enumerate(values):
        gradient_bar(ax, i, v, width=0.50)

    x = np.arange(len(years))
    ax.plot(x, values, color=line_color, lw=2.4, zorder=4)
    ax.scatter(
        x,
        values,
        s=90,
        color=marker_color,
        zorder=5,
        edgecolors="white",
        linewidths=0.8,
    )

    offset = max(ymax * 0.02, 0.18)
    for xi, yi in zip(x, values):
        label = f"{yi:.1f}" if float(yi) != int(yi) else str(int(yi))
        ax.text(
            xi,
            yi + offset,
            label,
            ha="center",
            va="bottom",
            fontsize=value_fontsize,
            color=brand_blue,
            fontweight="bold",
            zorder=6,
        )


def draw_title_banner(fig, box, title_text, font_size=18):
    title_ax = fig.add_axes(box)
    title_ax.set_axis_off()

    grad = make_horizontal_gradient(1200)
    im = title_ax.imshow(grad, extent=[0, 1, 0, 1], origin="lower", aspect="auto")

    poly_pts = np.array(
        [
            [0.00, 0.14],
            [0.91, 0.14],
            [0.995, 0.50],
            [0.91, 0.86],
            [0.00, 0.86],
        ]
    )
    poly = Polygon(poly_pts, closed=True, transform=title_ax.transAxes, facecolor="none")
    im.set_clip_path(poly)

    title_ax.text(
        0.035,
        0.50,
        title_text,
        color="white",
        fontsize=font_size,
        fontweight="bold",
        va="center",
        ha="left",
        transform=title_ax.transAxes,
        fontproperties=CH_FONT,
    )


def draw_metric_chip(ax, x, y, text, width=0.42, height=0.62, fontsize=14):
    chip = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.03",
        linewidth=1.0,
        edgecolor="#D9DEEA",
        facecolor="#F8F9FC",
    )
    ax.add_patch(chip)

    ax.text(
        x + 0.03,
        y + height / 2,
        "◎",
        fontsize=fontsize + 1,
        color=brand_blue,
        va="center",
        ha="left",
        fontproperties=CH_FONT,
    )

    ax.text(
        x + 0.07,
        y + height / 2,
        text,
        fontsize=fontsize,
        color=text_color,
        va="center",
        ha="left",
        fontproperties=CH_FONT,
    )


def draw_footer_text(fig, box, left_lines, right_lines, line_size=13):
    txt_ax = fig.add_axes(box, facecolor=bg_color)
    txt_ax.set_axis_off()
    if left_lines:
        draw_metric_chip(txt_ax, 0.01, 0.18, left_lines[0], width=0.46, height=0.62, fontsize=line_size)
    if right_lines:
        draw_metric_chip(txt_ax, 0.52, 0.18, right_lines[0], width=0.42, height=0.62, fontsize=line_size)


# =========================
# 版式函数
# =========================
def create_wechat_235(spec: ChartSpec, output_path: str | Path):
    output_path = Path(output_path)
    fig = plt.figure(figsize=(11.75, 5.0), facecolor=bg_color)
    draw_title_banner(fig, box=[0.06, 0.84, 0.44, 0.10], title_text=spec.main_title, font_size=18)
    draw_logo(fig, box=[0.70, 0.80, 0.30, 0.25], logo_path=_resolve_brand_logo_path(spec))

    fig.text(0.06, 0.77, spec.journal_title, fontsize=15, color="#46506A", ha="left", va="center")

    chart_ax = fig.add_axes([0.06, 0.25, 0.88, 0.47], facecolor=bg_color)
    draw_chart(chart_ax, spec.years, spec.values, x_label_size=12, value_fontsize=13)
    draw_footer_text(fig, box=[0.06, 0.07, 0.88, 0.11], left_lines=spec.left_lines, right_lines=spec.right_lines, line_size=13)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return output_path


def create_xiaohongshu_3x4(spec: ChartSpec, output_path: str | Path):
    output_path = Path(output_path)
    fig = plt.figure(figsize=(7.2, 9.6), facecolor=bg_color)
    draw_title_banner(fig, box=[0.08, 0.89, 0.58, 0.070], title_text=spec.main_title, font_size=18)
    draw_logo(fig, box=[0.70, 0.80, 0.25, 0.21], logo_path=_resolve_brand_logo_path(spec))

    fig.text(0.08, 0.83, spec.journal_title, fontsize=15, color="#46506A", ha="left", va="center")
    chart_ax = fig.add_axes([0.10, 0.37, 0.82, 0.39], facecolor=bg_color)
    draw_chart(chart_ax, spec.years, spec.values, x_label_size=13, value_fontsize=14)

    txt_ax = fig.add_axes([0.08, 0.20, 0.84, 0.10], facecolor=bg_color)
    txt_ax.set_axis_off()
    if spec.left_lines:
        draw_metric_chip(txt_ax, 0.00, 0.18, spec.left_lines[0], width=0.48, height=0.62, fontsize=14)
    if spec.right_lines:
        draw_metric_chip(txt_ax, 0.50, 0.18, spec.right_lines[0], width=0.46, height=0.62, fontsize=14)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return output_path


def _normalize_variant(variant: str) -> str:
    normalized = variant.strip().lower().replace("-", "_")
    if normalized in {"wechat", "wechat235", "wechat_235"}:
        return "wechat_235"
    if normalized in {"xiaohongshu", "xhs", "xhs_3x4", "xiaohongshu_3x4"}:
        return "xiaohongshu_3x4"
    raise ValueError(f"不支持的图表 variant: {variant}")


def render_chart(spec: ChartSpec, output_path: str | Path) -> Path:
    variant = _normalize_variant(spec.variant)
    if variant == "wechat_235":
        return create_wechat_235(spec, output_path)
    if variant == "xiaohongshu_3x4":
        return create_xiaohongshu_3x4(spec, output_path)
    raise ValueError(f"不支持的图表 variant: {spec.variant}")


def _clone_spec_for_variant(spec: ChartSpec, variant: str) -> ChartSpec:
    return replace(spec, variant=_normalize_variant(variant))


def load_chart_specs(config_path: str | Path) -> dict[str, ChartSpec]:
    config_path = Path(config_path)
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    journal_title = str(raw.get("journal_title", "")).strip()
    charts = raw.get("charts", {}) or {}
    if not isinstance(charts, dict):
        raise ValueError("chart_config.json 中的 charts 必须是对象")

    specs: dict[str, ChartSpec] = {}
    for chart_name, chart_data in charts.items():
        if not isinstance(chart_data, dict):
            raise ValueError(f"图表配置必须是对象: {chart_name}")
        spec = ChartSpec.from_config(journal_title, chart_data)
        specs[str(chart_name).strip()] = spec
    return specs


def _sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", name).strip("_")
    return safe or "chart"


def generate_charts_from_config(
    config_path: str | Path,
    output_dir: str | Path,
    xhs_output_dir: str | Path | None = None,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    config_path = Path(config_path)
    if xhs_output_dir is None:
        xhs_output_dir = config_path.parent / "xhs"
    xhs_output_dir = Path(xhs_output_dir)
    specs = load_chart_specs(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    xhs_output_dir.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, Path] = {}
    for chart_name, spec in specs.items():
        safe_name = _sanitize_filename(chart_name)

        wechat_spec = _clone_spec_for_variant(spec, "wechat_235")
        wechat_output_path = output_dir / f"{safe_name}_wechat_235.png"
        outputs[chart_name] = render_chart(wechat_spec, wechat_output_path)

        xhs_spec = _clone_spec_for_variant(spec, "xiaohongshu_3x4")
        xhs_output_path = xhs_output_dir / f"{safe_name}_xiaohongshu_3x4.png"
        render_chart(xhs_spec, xhs_output_path)
    return outputs


if __name__ == "__main__":
    demo_spec = ChartSpec(
        journal_title="IEEE/ACM Transactions on the Web",
        main_title="四、影响因子（IF）五年趋势分析",
        years=[2020, 2021, 2022, 2023, 2024],
        values=[6.5, 8.2, 7.3, 8.4, 9.7],
        left_lines=["最新影响因子：2024年为9.7"],
        right_lines=["影响因子区间：6.5–9.7"],
        variant="wechat_235",
    )
    create_wechat_235(demo_spec, "if_trend_wechat_235.png")

    demo_xhs_spec = ChartSpec(
        journal_title=demo_spec.journal_title,
        main_title=demo_spec.main_title,
        years=demo_spec.years,
        values=demo_spec.values,
        left_lines=demo_spec.left_lines,
        right_lines=demo_spec.right_lines,
        variant="xiaohongshu_3x4",
    )
    create_xiaohongshu_3x4(demo_xhs_spec, "if_trend_xiaohongshu_3x4.png")
