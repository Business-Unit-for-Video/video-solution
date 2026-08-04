"""Simple CLI entrypoints for pipeline tasks."""
from pathlib import Path
import argparse
import json

from .content_package import (
    MODES,
    build_validation_report,
    load_content_package,
    validate_content_package,
)
from .fetch_list import fetch_channel_list


def main():
    p = argparse.ArgumentParser(description="视频处理管道命令行工具")
    p.add_argument("cmd", choices=["fetch-list", "validate-content"], help="要执行的命令")
    p.add_argument("--channel-url", required=False, help="YouTube 频道/播放列表 URL（fetch-list 命令必需）")
    p.add_argument("--out", default="output/list.json", help="输出文件路径")
    p.add_argument("--format", choices=["json", "csv"], default="json", help="输出格式")
    p.add_argument("--cookies", default=None, help="cookies.txt 路径（Netscape 格式），直接传文件路径，不要 base64")
    p.add_argument("--package", help="内容包 JSON 路径（validate-content 命令必需）")
    p.add_argument("--mode", choices=sorted(MODES), default="validate", help="内容包校验模式")
    p.add_argument("--report", help="可选的 JSON 校验报告输出路径")
    args = p.parse_args()

    if args.cmd == "fetch-list":
        if not args.channel_url:
            p.error("--channel-url is required for fetch-list command")
        
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        result = fetch_channel_list(
            channel_url=args.channel_url,
            out_path=args.out,
            out_format=args.format,
            cookies_path=args.cookies
        )
        print(f"✓ 成功获取 {len(result)} 个视频，保存到 {args.out}")

    if args.cmd == "validate-content":
        if not args.package:
            p.error("--package is required for validate-content command")

        package = load_content_package(args.package)
        issues = validate_content_package(package, mode=args.mode)
        report = build_validation_report(package, args.mode, issues)

        if args.report:
            report_path = Path(args.report)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not report["valid"]:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
