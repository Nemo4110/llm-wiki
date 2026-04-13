"""
LLM-Wiki 命令实现

与 Claude Code 集成的具体命令。
"""

from pathlib import Path
from typing import Optional
import click

from .core import WikiManager, find_wiki_root, IngestResult


@click.group()
@click.option('--wiki-dir', type=click.Path(), help='Wiki 目录路径')
@click.pass_context
def cli(ctx, wiki_dir: Optional[str]):
    """LLM-Wiki 命令行工具"""
    if wiki_dir:
        root = Path(wiki_dir)
    else:
        root = find_wiki_root()

    if not root:
        click.echo("错误：找不到 wiki 根目录。请确保当前目录在 wiki 内，或指定 --wiki-dir")
        ctx.exit(1)

    ctx.ensure_object(dict)
    ctx.obj['wiki'] = WikiManager(root / "wiki")
    ctx.obj['root'] = root


@cli.command()
@click.argument('source_path', type=click.Path(exists=True))
@click.option('--dry-run', is_flag=True, help='预览但不实际修改')
@click.pass_context
def ingest(ctx, source_path: str, dry_run: bool):
    """
    摄取资料到 wiki

    示例：
        wiki ingest sources/paper.pdf
        wiki ingest sources/笔记.md --dry-run
    """
    wiki = ctx.obj['wiki']
    root = ctx.obj['root']
    source = Path(source_path)

    # 读取资料内容
    click.echo(f"正在读取: {source}")

    if dry_run:
        click.echo("【模拟模式】将执行以下操作：")
        click.echo(f"  - 分析 {source.name}")
        click.echo(f"  - 识别相关 wiki 页面")
        click.echo(f"  - 创建/更新页面")
        click.echo(f"  - 追加到 log.md")
        return

    # 实际逻辑由 LLM 通过工具调用完成
    # 这里只提供 CLI 接口
    click.echo(f"请使用自然语言指令：")
    click.echo(f'  "请摄入资料 {source.name} 到 wiki"')


@cli.command()
@click.argument('query_text')
@click.option('--save', is_flag=True, help='将回答保存为新页面')
@click.pass_context
def query(ctx, query_text: str, save: bool):
    """
    查询 wiki 知识库

    示例：
        wiki query "Transformer 的工作原理"
        wiki query "LoRA 和全量微调的区别" --save
    """
    wiki = ctx.obj['wiki']

    click.echo(f"查询: {query_text}")

    # 列出可用页面供参考
    pages = wiki.list_pages()
    if pages:
        click.echo(f"\n当前 wiki 有 {len(pages)} 个页面:")
        for p in pages[:10]:
            click.echo(f"  - {p.title}")
        if len(pages) > 10:
            click.echo(f"  ... 还有 {len(pages) - 10} 个")

    click.echo(f"\n请使用自然语言指令：")
    click.echo(f'  "查询 wiki: {query_text}"')
    if save:
        click.echo(f'  （添加 --save 会将结果存档）')


@cli.command()
@click.option('--fix', is_flag=True, help='尝试自动修复问题')
@click.pass_context
def lint(ctx, fix: bool):
    """
    检查 wiki 健康状况

    检查项：
      - 孤儿页面（未被引用的页面）
      - 死链（指向不存在的页面）
      - 陈旧页面（90天未更新）
      - 草稿页面
    """
    wiki = ctx.obj['wiki']

    click.echo("正在检查 wiki 健康状况...\n")

    issues = wiki.lint()

    has_issues = any(issues.values())

    if not has_issues:
        click.echo("✓ 健康状况良好！")
        return

    # 报告问题
    if issues['orphans']:
        click.echo(f"⚠️  孤儿页面 ({len(issues['orphans'])}):")
        for p in issues['orphans'][:5]:
            click.echo(f"    - {p}")
        if len(issues['orphans']) > 5:
            click.echo(f"    ... 还有 {len(issues['orphans']) - 5} 个")

    if issues['dead_links']:
        click.echo(f"\n⚠️  死链 ({len(issues['dead_links'])}):")
        for link in issues['dead_links'][:5]:
            click.echo(f"    - [[{link}]]")

    if issues['stale']:
        click.echo(f"\n📅 陈旧页面 ({len(issues['stale'])}):")
        for p in issues['stale'][:5]:
            click.echo(f"    - {p}")

    if issues['drafts']:
        click.echo(f"\n📝 草稿页面 ({len(issues['drafts'])}):")
        for p in issues['drafts'][:5]:
            click.echo(f"    - {p}")

    click.echo(f"\n请使用自然语言指令修复：")
    click.echo(f'  "请修复 wiki 中的问题"')


@cli.command()
@click.pass_context
def status(ctx):
    """查看 wiki 状态概览"""
    wiki = ctx.obj['wiki']
    root = ctx.obj['root']

    pages = wiki.list_pages()
    recent_logs = wiki.read_log(5)

    click.echo(f"📚 Wiki 根目录: {root}")
    click.echo(f"📄 总页面数: {len(pages)}")

    # 状态统计
    status_count = {}
    for p in pages:
        s = p.status
        status_count[s] = status_count.get(s, 0) + 1

    click.echo(f"\n页面状态:")
    for status, count in status_count.items():
        click.echo(f"  - {status}: {count}")

    click.echo(f"\n最近活动:")
    for entry in recent_logs:
        # 简化显示
        lines = entry.strip().split('\n')
        if lines:
            click.echo(f"  {lines[0]}")


if __name__ == '__main__':
    cli()
