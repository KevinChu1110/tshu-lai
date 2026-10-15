"""臺灣民間節日表（農曆）與用台語講的提醒。和 MCP 分開，方便測試。"""

from __future__ import annotations

from datetime import date, timedelta

from lunar_python import Solar

# (農曆月, 日) -> (名稱, 阿嬤會講的話)
LUNAR = {
    (1, 1): ("過年", "新年恭喜，紅包有提著無？"),
    (1, 9): ("天公生", "今仔日天公生，愛拜天公"),
    (1, 15): ("元宵", "元宵愛食圓仔"),
    (2, 2): ("土地公生", "今仔日土地公生，頭牙"),
    (3, 23): ("媽祖生", "媽祖生，廟口足鬧熱"),
    (5, 5): ("五日節", "五日節，粽縛好矣"),
    (7, 1): ("開鬼門", "七月開始矣，暗時較少出門"),
    (7, 15): ("中元普渡", "今仔日普渡，愛拜好兄弟"),
    (8, 15): ("中秋", "中秋，月餅佮柚仔"),
    (9, 9): ("重陽", "重陽節，老人節"),
    (12, 16): ("尾牙", "尾牙，食刈包"),
    (12, 24): ("送神", "今仔日送神"),
}
SOLAR_TERMS = {"清明": "清明愛去掃墓", "冬至": "冬至愛食圓仔，食了加一歲"}


def festivals_on(d: date) -> list[tuple[str, str]]:
    lunar = Solar.fromYmd(d.year, d.month, d.day).getLunar()
    out = []
    m, day = abs(lunar.getMonth()), lunar.getDay()   # 閏月是負數；閏月不過節
    if lunar.getMonth() > 0 and (m, day) in LUNAR:
        out.append(LUNAR[(m, day)])
    nxt = (d + timedelta(days=1))
    nl = Solar.fromYmd(nxt.year, nxt.month, nxt.day).getLunar()
    if nl.getMonth() == 1 and nl.getDay() == 1:
        out.append(("除夕", "今暗圍爐，攏愛轉來食飯"))
    jq = lunar.getJieQi()
    if jq in SOLAR_TERMS:
        out.append((jq, SOLAR_TERMS[jq]))
    if lunar.getMonth() > 0 and day in (1, 15) and not out:
        out.append(("初一" if day == 1 else "十五", "今仔日初一，愛拜拜" if day == 1 else "今仔日十五，愛拜拜"))
    return out


def topics_for(d: date, lookahead: int = 3) -> list[str]:
    out = [say for _, say in festivals_on(d)]
    words = {1: "明仔載", 2: "後日", 3: "大後日"}
    for i in range(1, lookahead + 1):
        for name, _ in festivals_on(d + timedelta(days=i)):
            if name not in ("初一", "十五"):
                out.append(f"{words[i]}就是{name}矣")
    return out
