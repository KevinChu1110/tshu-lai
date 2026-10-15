"""tshulai-capture 指令列。"""

from __future__ import annotations

from pathlib import Path

import typer
from rich import print as rprint
from rich.table import Table

from . import audio, index, interview, layout

app = typer.Typer(help="厝內 階段 0：採集整理工具", no_args_is_help=True)


@app.command()
def init(root: Path = typer.Argument(Path("data"))):
    """建立標準 data/ 資料夾結構。"""
    created = layout.ensure_layout(root)
    for d in created:
        rprint(f"[green]建立[/] {d}")
    if not created:
        rprint("資料夾都在了。")


@app.command()
def check(root: Path = typer.Argument(Path("data"))):
    """檢查檔名是否照規則、檔案是否放對資料夾。"""
    items = layout.scan(root)
    bad = 0
    for it in items:
        problems = []
        if not it.name_ok:
            problems.append("檔名不合規則")
        if it.category.startswith("audio") and it.kind not in ("audio", "video"):
            problems.append("不是音訊")
        if it.category.startswith("video") and it.kind != "video":
            problems.append("不是影片")
        if it.category.startswith("photo") and it.kind != "photo":
            problems.append("不是照片")
        if problems:
            bad += 1
            rprint(f"[yellow]{it.path.relative_to(root)}[/]  {'；'.join(problems)}")
    rprint(f"共 {len(items)} 個檔案，{bad} 個有問題。")


@app.command()
def normalize(
    root: Path = typer.Argument(Path("data")),
    split: bool = typer.Option(True, help="依靜音切成 3 到 15 秒段落"),
):
    """把 audio/ 和 video/talking 轉成 16kHz WAV，放到 work/wav/，可選切段到 work/segments/。"""
    items = [i for i in layout.scan(root) if i.category.startswith("audio") or i.category == "video/talking"]
    wav_dir, seg_dir = root / "work" / "wav", root / "work" / "segments"
    for it in items:
        dst = wav_dir / it.category / f"{it.path.stem}.wav"
        if dst.exists():
            continue
        audio.to_wav16k(it.path, dst)
        msg = f"[green]轉檔[/] {it.path.name} -> {dst.relative_to(root)}"
        if split and it.category in ("audio/story", "audio/chat"):
            segs = audio.split_on_silence(dst, seg_dir / it.category)
            msg += f"，切 {len(segs)} 段"
        rprint(msg)


@app.command()
def transcribe(root: Path = typer.Argument(Path("data"))):
    """對 work/wav/ 下的檔案跑語音辨識，輸出到 work/transcripts/。"""
    from . import transcribe as tr

    wav_dir, out_dir = root / "work" / "wav", root / "work" / "transcripts"
    for wav in sorted(wav_dir.rglob("*.wav")) if wav_dir.exists() else []:
        out = out_dir / f"{wav.stem}.json"
        if out.exists():
            continue
        segs = tr.transcribe(wav, out)
        rprint(f"[green]轉寫[/] {wav.name}：{len(segs)} 句")


@app.command("index")
def index_cmd(root: Path = typer.Argument(Path("data"))):
    """合併逐字稿與 notes/log.md，輸出 work/stories.jsonl。"""
    out = root / "work" / "stories.jsonl"
    n = index.build(root, out)
    rprint(f"寫入 {n} 筆到 {out}")


@app.command("poj-draft")
def poj_draft(
    root: Path = typer.Argument(Path("data")),
    ollama: str = typer.Option("", help="跑 Taigi 翻譯模型的 Ollama 網址，例 http://127.0.0.1:11434；空白就只產生空的白話字欄"),
    model: str = typer.Option("taigi-translator"),
):
    """逐字稿 → 白話字草稿 TSV（work/poj/），給家人邊聽邊校正。"""
    from . import poj

    for p in poj.draft(root, ollama or None, model):
        rprint(f"[green]草稿[/] {p.relative_to(root)}")
    rprint("用試算表或文字編輯器打開 TSV，邊聽邊改 poj 欄，改好的那行 checked 填 1。")


@app.command("poj-export")
def poj_export(root: Path = typer.Argument(Path("data")), speaker: str = "ama"):
    """校正過的段落 → GPT-SoVITS 訓練清單 work/tts_train.list。"""
    from . import poj

    out, n, skipped = poj.export(root, speaker)
    rprint(f"收錄 {n} 段，略過 {skipped} 段（未校正或長度不在 1 到 15 秒），清單：{out}")


@app.command("interview")
def interview_cmd(
    topic: str = typer.Option(None, help="主題 id 或名稱，不給就列出全部主題"),
    name: str = typer.Option("", help="親戚主題時代入的稱呼"),
    user: str = typer.Option("你", help="她對使用者的稱呼"),
):
    """印出訪談題目。"""
    topics = interview.load()
    if not topic:
        for t in topics:
            rprint(f"[bold]{t['id']}[/]  {t['name']}  ({len(t['questions'])} 題)" + (f"  [dim]{t['note']}[/]" if t.get("note") else ""))
        return
    t = interview.find_topic(topics, topic)
    if not t:
        raise typer.BadParameter(f"沒有這個主題：{topic}")
    rprint(f"[bold]{t['name']}[/]")
    if t.get("note"):
        rprint(f"[dim]{t['note']}[/]")
    for i, q in enumerate(t["questions"], 1):
        text = q["q"].replace("{name}", name or "○○").replace("{user}", user)
        rprint(f"{i}. {text}")
        if q.get("purpose"):
            rprint(f"   [dim]{q['purpose']}[/]")


@app.command()
def progress(root: Path = typer.Argument(Path("data"))):
    """統計採集進度。"""
    items = layout.scan(root)
    table = Table(title="採集進度")
    table.add_column("項目")
    table.add_column("目標", justify="right")
    table.add_column("已完成", justify="right")
    for category, (desc, target, unit) in layout.LAYOUT.items():
        mine = [i for i in items if i.category == category]
        if unit == "分鐘":
            done = 0.0
            for i in mine:
                try:
                    done += audio.duration_seconds(i.path) / 60
                except Exception:
                    pass
            done_s = f"{done:.0f} 分鐘"
        else:
            done_s = f"{len(mine)} {unit}"
        target_s = f"{target:g} {unit}" if target else "越多越好"
        table.add_row(desc, target_s, done_s)
    rprint(table)


if __name__ == "__main__":
    app()
