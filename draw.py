import cairo
from datetime import datetime, timedelta
from typing import Dict, Any, TypedDict
import os
import math
from enum import IntEnum

class PlotType(IntEnum):
    SHOW_ALL = 0
    SOLAR_AND_OTHER = 1
    RENEWABLE_AND_OTHER = 2
    LNG_COAL_AND_OTHER = 3

POWER_TYPE = {
    "NUCLEAR":           "nuclear",
    "COAL":              "coal",
    "COGEN":             "cogen",
    "IPPCOAL":           "ippcoal",
    "LNG":               "lng",
    "IPPLNG":            "ipplng",
    "OIL":               "oil",
    "DIESEL":            "diesel",
    "HYDRO":             "hydro",
    "WIND":              "wind",
    "SOLAR":             "solar",
    "OTHER_RENEWABLE":   "OtherRenewableEnergy",
    "ENERGY_STORAGE":    "EnergyStorageSystem",
}


class PowerData(TypedDict):
    nuclear: float
    coal: float
    cogen: float
    ippcoal: float
    lng: float
    ipplng: float
    oil: float
    diesel: float
    hydro: float
    wind: float
    solar: float
    OtherRenewableEnergy: float
    EnergyStorageSystem: float

def sum_power_data(data: PowerData) -> float:
    return data["nuclear"] + \
           data["coal"] + \
           data["cogen"] + \
           data["ippcoal"] + \
           data["lng"] + \
           data["ipplng"] + \
           data["oil"] + \
           data["diesel"] + \
           data["hydro"] + \
           data["wind"] + \
           data["solar"] + \
           data["OtherRenewableEnergy"] + \
           data["EnergyStorageSystem"]


def generate_time_intervals() -> list[str]:
    now = datetime.now()

    past = now - timedelta(hours=36)
    past = past.replace(minute=0, second=0, microsecond=0)

    intervals = []
    current = past

    while current <= now:
        intervals.append(current.isoformat()[:19])
        current += timedelta(minutes=10)

    return intervals

def get_latest_timestamp(data: Dict[str, Any]) -> str:
    """Returns the latest timestamp key from a dictionary."""
    if not data:
        raise ValueError("Dictionary cannot be empty")

    return max(data.keys())

def get_pat_path(idx):
    pattern_base_path = os.path.join("www", "img")
    return os.path.join(pattern_base_path, f"gray-{idx}.png")

def plot_generation(data, plot_type: PlotType, width: int, height: int) -> str:
    config_margin_top = 55
    config_margin_right = 24
    config_margin_bottom = 20
    config_margin_left = 10

    container_width  = width
    container_height = height

    chart_width = container_width - config_margin_left - config_margin_right
    chart_height = container_height - config_margin_top - config_margin_bottom

    time_intervals = generate_time_intervals()

    svg_path = os.path.join("www", f"plot_{width}x{height}.svg")

    svg_surface = cairo.SVGSurface(svg_path, container_width, container_height)

    ctx = cairo.Context(svg_surface)

    ctx.save()
    ctx.translate(config_margin_left, config_margin_top)

    max_value = max(
        sum(data[interval].values()) if interval in data else 0
        for interval in time_intervals
    )
    y_axis_steps = 5000
    max_axis_value = math.ceil(max_value / y_axis_steps) * y_axis_steps

    latest_time_stamp = get_latest_timestamp(data)

    bar_width = chart_width / len(time_intervals)
    value_scale = chart_height / max_axis_value

    generation_path_top = []
    generation_path_bot = []
    generation_name    = None
    generation_pattern = None
    generation_time    = []

    cnt = 0
    if (plot_type == PlotType.SHOW_ALL):
        cnt = 7
    elif (plot_type == PlotType.SOLAR_AND_OTHER):
        cnt = 2
    elif (plot_type == PlotType.RENEWABLE_AND_OTHER):
        cnt = 2
    elif (plot_type == PlotType.LNG_COAL_AND_OTHER):
        cnt = 3

    for i in range(cnt):
        generation_path_top.append([])
        generation_path_bot.append([])

    default_data: PowerData = {
        "nuclear": 0,
        "coal": 0,
        "cogen": 0,
        "ippcoal": 0,
        "lng": 0,
        "ipplng": 0,
        "oil": 0,
        "diesel": 0,
        "hydro": 0,
        "wind": 0,
        "solar": 0,
        "OtherRenewableEnergy": 0,
        "EnergyStorageSystem": 0,
    }

    for idx, time in enumerate(time_intervals):
        time_obj = datetime.fromisoformat(time.replace('Z', ''))
        x = idx * bar_width
        if time in data:
            total_generation = sum(data[time].values())
            bar_height = total_generation * value_scale
            curr = data[time]
        else:
            bar_height = 0
            curr = default_data

        y = chart_height - bar_height

        if time_obj.minute == 0 and time_obj.hour % 6 == 0:
            formatted_time = time.replace('T', ' ')[5:16]
            generation_time.append((x, formatted_time))

        generation = []

        if plot_type == PlotType.SHOW_ALL:
            generation.extend([
                curr["coal"] + curr["ippcoal"] + curr["cogen"],
                curr["lng"] + curr["ipplng"],
                curr["oil"] + curr["diesel"],
                curr["hydro"],
                curr["wind"],
                curr["solar"],
                curr["nuclear"] + curr["OtherRenewableEnergy"] + curr["EnergyStorageSystem"]
            ])
        elif plot_type == PlotType.SOLAR_AND_OTHER:
            generation.extend([
                sum_power_data(curr) - curr["solar"],
                curr["solar"]
            ])
        elif plot_type == PlotType.RENEWABLE_AND_OTHER:
            generation.extend([
                curr["coal"] + curr["ippcoal"] + curr["cogen"] +
                curr["lng"] + curr["ipplng"] + curr["oil"] + curr["diesel"],
                curr["solar"] + curr["hydro"] + curr["wind"] +
                curr["nuclear"] + curr["OtherRenewableEnergy"] + curr["EnergyStorageSystem"]
            ])
        elif plot_type == PlotType.LNG_COAL_AND_OTHER:
            generation.extend([
                curr["coal"] + curr["ippcoal"] + curr["cogen"],
                curr["lng"] + curr["ipplng"] + curr["oil"] + curr["diesel"],
                curr["solar"] + curr["hydro"] + curr["wind"] +
                curr["nuclear"] + curr["OtherRenewableEnergy"] + curr["EnergyStorageSystem"]
            ])
        generation.reverse()

        for i, value in enumerate(generation):
            bar_height = value * value_scale
            generation_path_top[i].extend([(x, y), (x + bar_width, y)])
            generation_path_bot[i].extend([(x, y + bar_height), (x + bar_width, y + bar_height)])
            y += bar_height


    # Combine top and reversed bottom paths
    generation_path = []
    for i in range(len(generation_path_bot)):
        combined_path = generation_path_top[i] + generation_path_bot[i][::-1]
        generation_path.append(combined_path)

    # Set names and patterns based on plot type
    if plot_type == PlotType.SHOW_ALL:
        generation_name = ["燃煤", "燃氣", "燃油",
                         "水力", "風力", "太陽能",
                         "核能、其他再生、儲能"]
        generation_pattern = [1, 2, 3, 4, 5, 6, 7]
    elif plot_type == PlotType.SOLAR_AND_OTHER:
        generation_name = ["其他", "太陽能"]
        generation_pattern = [2, 6]
    elif plot_type == PlotType.RENEWABLE_AND_OTHER:
        generation_name = ["化石燃料", "再生能源"]
        generation_pattern = [2, 6]
    elif plot_type == PlotType.LNG_COAL_AND_OTHER:
        generation_name = ["燃煤", "燃氣、燃油", "其他"]
        generation_pattern = [1, 4, 6]

    # Reverse to match drawing order
    generation_name.reverse()
    generation_pattern.reverse()

    for idx, points in enumerate(generation_path):
        if not points:
            continue

        # Create pattern from image
        surface = cairo.ImageSurface.create_from_png(get_pat_path(generation_pattern[idx]))
        pattern = cairo.SurfacePattern(surface)
        pattern.set_extend(cairo.Extend.REPEAT)

        # Draw the path
        ctx.new_path()
        for i, (x, y) in enumerate(points):
            if i == 0:
                ctx.move_to(x, y)
            else:
                ctx.line_to(x, y)
        ctx.close_path()

        # Set style and fill
        ctx.set_source(pattern)
        ctx.fill_preserve()
        ctx.set_line_width(0.2)
        ctx.set_source_rgb(0, 0, 0)  # Black stroke
        ctx.stroke()

        # Set up text style
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(12)

    for idx, (curr_x, time) in enumerate(generation_time):
        # Calculate text position
        ctx.set_source_rgb(0, 0, 0)
        draw_flag = True
        text_x = curr_x
        if idx == len(generation_time) - 1:  # Last label
            # Get text extents for proper alignment
            extents = ctx.text_extents(time)
            if (chart_width - text_x) < extents.width:
                draw_flag = False

        if draw_flag:
            # Draw text
            ctx.move_to(text_x, chart_height + 12)
            ctx.show_text(time)

        # Draw vertical dashed line
        ctx.set_source_rgb(0.8, 0.8, 0.8)  # Light gray (#ccc)
        ctx.set_line_width(0.5)
        ctx.set_dash([2.0, 2.0])  # Dash pattern: 2 on, 2 off

        # line_top = margin_top
        # line_bottom = chart_height - margin_bottom
        ctx.move_to(curr_x, 0)
        ctx.line_to(curr_x, chart_height)
        ctx.stroke()

        # Reset dash pattern for next operations
        ctx.set_dash([])

    for value in range(0, int(max_axis_value) + 1, y_axis_steps):
        # Calculate positions
        scaled_value = value / 1000  # Convert to thousands
        curr_y = chart_height - (value * value_scale) + 3
        curr_y_line = chart_height - (value * value_scale)

        # Draw label (right aligned)
        ctx.move_to(chart_width + 1, curr_y)
        ctx.set_source_rgb(0, 0, 0)
        ctx.show_text(f"{int(scaled_value)}")

        # Draw horizontal dashed line
        ctx.set_source_rgb(0.8, 0.8, 0.8)  # Light gray (#ccc)
        ctx.set_line_width(0.5)
        ctx.set_dash([2.0, 2.0])  # 2px dash, 2px gap

        ctx.move_to(0, curr_y_line)
        ctx.line_to(chart_width, curr_y_line)
        ctx.stroke()

        # Reset dash for next operations
        ctx.set_dash([])

    ctx.select_font_face("Sans",
                         cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_source_rgb(0, 0, 0)  # Black text


    ctx.select_font_face("Noto Sans TC",
                         cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(12)
    ctx.set_source_rgb(0, 0, 0)
    x_pos = chart_width+config_margin_right
    y_pos = 0
    label = "百萬瓩"
    # Get text extents for proper alignment
    extents = ctx.text_extents(label)
    x_pos -= extents.width
    y_pos -= extents.height

    # Draw text
    ctx.move_to(x_pos, y_pos)
    ctx.show_text(label)


    # Calculate total legend width
    # legend_text_length = sum(len(name) for name in generation_name)
    # legend_text_width = legend_text_length * legend_text_width_per_char
    legend_circle_diameter = 12
    legend_circle_radius = legend_circle_diameter / 2
    legend_padding = 5
    legend_text_width = sum(ctx.text_extents(name).width for name in generation_name)
    legend_pad_circle_width  = (legend_circle_diameter + legend_padding * 2)
    legend_pad_circle_width *= len(generation_name)
    legend_width = legend_text_width + legend_pad_circle_width

    # Set starting position (centered)
    curr_x = (chart_width - legend_width) / 2
    legend_y_pos = -legend_circle_diameter - 4

    # Draw legend items in reverse order (to match original)
    for idx in reversed(range(len(generation_name))):
        name = generation_name[idx]
        pattern_num = generation_pattern[idx]
        pattern_path = get_pat_path(pattern_num)

        # Draw circle with pattern fill
        circle_x = curr_x + legend_circle_radius
        circle_y = legend_y_pos + legend_circle_radius

        # Load pattern image
        try:
            pattern_surface = cairo.ImageSurface.create_from_png(pattern_path)
            pattern = cairo.SurfacePattern(pattern_surface)
            pattern.set_extend(cairo.Extend.REPEAT)

            # Draw circle
            ctx.save()
            ctx.new_path()
            ctx.set_source(pattern)
            ctx.arc(circle_x, circle_y, legend_circle_radius, 0, 2 * 3.14159)
            ctx.fill_preserve()
            ctx.set_source_rgb(0, 0, 0)  # Black stroke
            ctx.set_line_width(0.2)
            ctx.stroke()
            ctx.restore()
        except:
            print(f"Could not load pattern image: {pattern_path}")

        # Draw text
        text_x = curr_x + legend_circle_diameter + legend_padding
        text_y = legend_y_pos + legend_circle_diameter - 2

        ctx.move_to(text_x, text_y)
        ctx.show_text(name)

        # Update x position for next item
        curr_x += ctx.text_extents(name).width + legend_padding * 2 + legend_circle_diameter

    ctx.restore()

    svg_surface.finish()

    return svg_path