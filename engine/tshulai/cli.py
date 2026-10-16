"""tshulai-engine 指令列。

  tshulai-engine serve                 啟動引擎（預設 127.0.0.1:8765，Tailscale 用 --host 0.0.0.0）
  tshulai-engine drive check           檢查 service account 能不能讀到共享資料夾、缺哪些子資料夾
  tshulai-engine drive sync            立刻同步一次
  tshulai-engine trips                 重掃旅行照片，印出最近幾趟
  tshulai-engine poses                 用 BiRefNet 建姿勢庫（需要 --extra vision）
  tshulai-engine warm-tts              預先合成招呼語與口頭禪（台語 TTS 很慢，先做好）
  tshulai-engine frame-url             印出阿嬤看板網址
"""

from __future__ import annotations

import argparse
import logging
import os
import sys


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="tshulai-engine", description="厝內 Persona Engine")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("serve")
    s.add_argument("--host", default=os.environ.get("TSHULAI_HOST", "127.0.0.1"))
    s.add_argument("--port", type=int, default=int(os.environ.get("TSHULAI_PORT", "8765")))
    d = sub.add_parser("drive")
    d.add_argument("action", choices=["check", "sync"])
    sub.add_parser("trips")
    sub.add_parser("poses")
    sub.add_parser("warm-tts")
    sub.add_parser("frame-url")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    if args.cmd in (None, "serve"):
        import uvicorn

        host = getattr(args, "host", "127.0.0.1")
        port = getattr(args, "port", 8765)
        # 不記請求網址：阿嬤看板的鑰匙在網址裡
        uvicorn.run("tshulai.main:app", host=host, port=port, access_log=os.environ.get("TSHULAI_ACCESS_LOG") == "1")
        return

    from .config import load_config

    cfg = load_config()
    if args.cmd == "drive":
        if not cfg.drive.enabled or not cfg.drive.folder_id:
            sys.exit("data/config.yaml 的 drive.enabled / drive.folder_id 還沒設，步驟見 docs/google-drive.md")
        from .storage.drive import DriveMirror, service_account_creds

        creds = service_account_creds(cfg.data_dir / cfg.drive.service_account)
        print(f"service account：{creds.service_account_email}")
        mirror = DriveMirror(creds, cfg.drive.folder_id, cfg.data_dir / "drive")
        if args.action == "check":
            try:
                missing = mirror.missing_folders()
            except Exception as e:
                sys.exit(f"讀不到資料夾：{e}\n請確認資料夾已用「檢視者」分享給上面那個 email。")
            print("資料夾結構完整" if not missing else "缺少資料夾（請在 Drive 上建立）：\n  " + "\n  ".join(missing))
        else:
            changed = mirror.sync()
            print(f"同步完成，{len(changed)} 個檔案變更")
        return

    from .main import Engine

    eng = Engine(cfg)
    if args.cmd == "trips":
        eng.refresh_media()
        for t in eng.memory.recent_trips(10):
            print(f"{t['start']}  {t['title']}  ({len(t['photos'])} 張)")
    elif args.cmd == "poses":
        from .vision.poses import PoseLibrary

        lib = PoseLibrary(cfg.data_dir / "poses")
        n = lib.build([root / "photo" / "pose" for root in cfg.media_roots])
        print(f"新增 {n} 張，姿勢庫共 {len(lib.index)} 張")
    elif args.cmd == "warm-tts":
        from .voice.pipeline import PhraseCache

        if not isinstance(eng.tts, PhraseCache):
            sys.exit("config 的 tts 要設成 taigi 才需要預先合成")
        sp = eng.persona.get("speech", {})
        phrases = list(sp.get("greetings", [])) + ["轉來矣喔？食飽未？", "緊入來坐", "路上愛細膩"]
        phrases += [f"{f}。" for f in sp.get("fillers", [])]
        print(f"合成 {eng.tts.warm(phrases)} 句")
    elif args.cmd == "frame-url":
        print(f"/frame?key={eng.frame_key}")


if __name__ == "__main__":
    main()
