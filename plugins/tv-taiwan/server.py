import os
from datetime import datetime
from pathlib import Path

from mcp.server.mcpserver import MCPServer

import schedule as sched

mcp = MCPServer("tv-taiwan")
PATH = Path(os.environ.get("TSHULAI_TV_SCHEDULE", "tv-schedule.yaml"))


@mcp.tool()
def schedule() -> str:
    """阿嬤的節目表。"""
    shows = sched.load(PATH)
    return "\n".join(f"{s.name}（{s.channel}）{s.start:%H:%M}-{s.end:%H:%M} 禮拜{s.weekdays}" for s in shows) or "還沒填節目表"


@mcp.tool()
def topics() -> str:
    """今天的節目話題，每行一個。"""
    return "\n".join(sched.topics(sched.load(PATH), datetime.now()))


@mcp.tool()
def poll_events() -> str:
    """節目開始或結束時回傳 tv.program_started / tv.program_ended。"""
    return "\n".join(sched.events(sched.load(PATH), datetime.now()))


if __name__ == "__main__":
    mcp.run()
