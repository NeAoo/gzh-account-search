"""Command-line entrypoint for gzh-account-search."""

import argparse
import sys
from pathlib import Path

from loguru import logger

from gzh_account_search import Config, Pipeline


def setup_logger(log_file: str, level: str = "INFO") -> None:
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | <level>{message}</level>"
        ),
        colorize=True,
    )
    logger.add(
        str(log_path),
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="按指定微信公众号名称批量采集文章并输出 Markdown 报告"
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        help="配置文件路径，默认 config.yaml",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="日志级别，默认 INFO",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        config = Config.from_yaml(args.config)
    except Exception as exc:
        print(f"配置加载失败: {exc}", file=sys.stderr)
        return 2

    setup_logger(config.paths.log_file, level=args.log_level)
    try:
        output_file = Pipeline(config).run()
    except Exception as exc:
        logger.error(f"运行失败: {exc}", exc_info=True)
        return 1

    if not output_file:
        logger.error("未生成报告")
        return 1

    logger.info(f"报告已生成: {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
