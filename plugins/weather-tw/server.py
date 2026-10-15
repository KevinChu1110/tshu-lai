"""weather-tw：tshu-lai knowledge + trigger plugin 範例。

座標從環境變數 TSHULAI_HOME_LAT / TSHULAI_HOME_LNG 讀（manifest 的 server.env），
引擎會用人格卡 home 的座標覆蓋。
"""

import json
import os
import urllib.request

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("weather-tw")
LAT = float(os.environ.get("TSHULAI_HOME_LAT", "23.5"))
LNG = float(os.environ.get("TSHULAI_HOME_LNG", "120.5"))

WMO_RAIN = set(range(51, 68)) | set(range(80, 83)) | {95, 96, 99}


def _fetch() -> dict:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LNG}&timezone=Asia%2FTaipei&forecast_days=1"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        "&hourly=precipitation_probability,weather_code&current=temperature_2m,weather_code"
    )
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


@mcp.tool()
def forecast() -> str:
    """今天阿嬤家的天氣摘要。"""
    d = _fetch()
    day = d["daily"]
    return (f"現在 {d['current']['temperature_2m']:.0f} 度，今天 {day['temperature_2m_min'][0]:.0f} 到 "
            f"{day['temperature_2m_max'][0]:.0f} 度，降雨機率 {day['precipitation_probability_max'][0]}%")


@mcp.tool()
def topics() -> str:
    """今天跟天氣有關、她可能會念的話題，每行一個。"""
    d = _fetch()["daily"]
    hi, lo, rain = d["temperature_2m_max"][0], d["temperature_2m_min"][0], d["precipitation_probability_max"][0]
    out = []
    if hi >= 33:
        out.append(f"今仔日足熱，{hi:.0f} 度，叫人愛啉水")
    if lo <= 14:
        out.append(f"今仔日寒，{lo:.0f} 度，叫人愛穿較燒")
    if rain >= 60:
        out.append("今仔日會落雨，出門愛紮雨傘")
    if not out:
        out.append(f"今仔日天氣袂䆀，{lo:.0f} 到 {hi:.0f} 度")
    return "\n".join(out)


@mcp.tool()
def poll_events() -> str:
    """兩小時內降雨機率超過 70% 時回傳 weather.rain_soon。"""
    from datetime import datetime

    d = _fetch()["hourly"]
    now = datetime.now().strftime("%Y-%m-%dT%H:00")
    if now not in d["time"]:
        return ""
    i = d["time"].index(now)
    if max(d["precipitation_probability"][i:i + 3]) >= 70:
        return "weather.rain_soon"
    return ""


if __name__ == "__main__":
    mcp.run()
