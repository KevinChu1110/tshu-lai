from datetime import date, datetime

from mcp.server.mcpserver import MCPServer

from festivals import festivals_on, topics_for

mcp = MCPServer("calendar-tw")


@mcp.tool()
def today() -> str:
    """今天的農曆日期與節日。"""
    from lunar_python import Solar

    d = date.today()
    lunar = Solar.fromYmd(d.year, d.month, d.day).getLunar()
    names = "、".join(n for n, _ in festivals_on(d)) or "無節日"
    return f"農曆{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}，{names}"


@mcp.tool()
def topics() -> str:
    """今天與接下來三天的節日話題，每行一個。"""
    return "\n".join(topics_for(date.today()))


@mcp.tool()
def poll_events() -> str:
    """早上八點後，今天有節日就回傳 festival.today（引擎一天只處理一次）。"""
    if datetime.now().hour >= 8 and festivals_on(date.today()):
        return "festival.today"
    return ""


if __name__ == "__main__":
    mcp.run()
