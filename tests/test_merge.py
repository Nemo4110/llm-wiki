"""
Tests for merge.py - Content Merge Strategies & Safe Writer
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from llm_wiki.merge import ContentMerger, MergeStrategy, SafeWriter, ChangeProposal
from llm_wiki.core import WikiManager, WikiPage


class TestContentMerger:
    """测试 ContentMerger 内容合并功能"""

    @pytest.fixture
    def temp_wiki(self, tmp_path):
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        return WikiManager(wiki_dir)

    @pytest.fixture
    def sample_page(self, temp_wiki):
        content = """# Transformer

基于注意力机制的序列建模架构。

## 核心要点

- 自注意力机制
- 多头注意力

## 详细说明

Transformer 使用 encoder-decoder 结构。

## 相关页面

- [[Attention]] — 注意力机制

## 来源

- [论文](../sources/paper.pdf)

## 变更日志

- 2026-04-10: 初始创建
"""
        path = temp_wiki.create_page(
            "Transformer",
            content,
            {"created": "2026-04-10", "updated": "2026-04-10", "tags": ["AI/ML"], "status": "active"},
        )
        return temp_wiki.get_page("Transformer")

    def test_append_after_section_existing(self, temp_wiki, sample_page):
        merger = ContentMerger(temp_wiki)
        result = merger.append_after_section(
            sample_page.content,
            "## 核心要点",
            "新增要点描述。",
        )
        assert "## 核心要点" in result
        assert "新增要点描述。" in result
        # 应该在"核心要点"和"详细说明"之间
        core_idx = result.index("## 核心要点")
        detail_idx = result.index("## 详细说明")
        new_idx = result.index("新增要点描述。")
        assert core_idx < new_idx < detail_idx

    def test_append_after_section_new(self, temp_wiki, sample_page):
        merger = ContentMerger(temp_wiki)
        result = merger.append_after_section(
            sample_page.content,
            "## 最新进展",
            "最新的研究成果。",
        )
        assert "## 最新进展" in result
        assert "最新的研究成果。" in result
        # 应该在"相关页面"之前
        related_idx = result.index("## 相关页面")
        new_idx = result.index("## 最新进展")
        assert new_idx < related_idx

    def test_add_related_link_existing_section(self, temp_wiki, sample_page):
        merger = ContentMerger(temp_wiki)
        result = merger.add_related_link(
            sample_page.content,
            "BERT",
            "基于 Transformer 的预训练模型",
        )
        assert "- [[BERT]] — 基于 Transformer 的预训练模型" in result
        # 不应该重复添加
        result2 = merger.add_related_link(
            result,
            "BERT",
            "基于 Transformer 的预训练模型",
        )
        assert result2 == result

    def test_add_related_link_new_section(self, temp_wiki):
        merger = ContentMerger(temp_wiki)
        content = "# Simple Page\n\n一句话定义。\n\n## 来源\n\n- [资料](../sources/x.pdf)\n"
        result = merger.add_related_link(content, "Other", "其他页面")
        assert "## 相关页面" in result
        assert "- [[Other]] — 其他页面" in result

    def test_append_changelog_existing(self, temp_wiki, sample_page):
        merger = ContentMerger(temp_wiki)
        result = merger.append_changelog(
            sample_page.content,
            "2026-04-21: 补充了多头注意力细节",
        )
        assert "2026-04-21: 补充了多头注意力细节" in result
        # 不应该重复添加
        result2 = merger.append_changelog(
            result,
            "2026-04-21: 补充了多头注意力细节",
        )
        assert result2 == result

    def test_append_changelog_new(self, temp_wiki):
        merger = ContentMerger(temp_wiki)
        content = "# Page\n\n定义。\n"
        result = merger.append_changelog(content, "2026-04-21: 初始创建")
        assert "## 变更日志" in result
        assert "2026-04-21: 初始创建" in result

    def test_generate_diff(self, temp_wiki):
        merger = ContentMerger(temp_wiki)
        original = "line 1\nline 2\nline 3\n"
        modified = "line 1\nline 2 modified\nline 3\n"
        diff = merger.generate_diff(original, modified)
        assert "--- original" in diff
        assert "+++ modified" in diff
        assert "line 2 modified" in diff

    def test_merge_link_only(self, temp_wiki, sample_page):
        merger = ContentMerger(temp_wiki)
        result = merger.merge(
            sample_page,
            "",
            MergeStrategy.LINK_ONLY,
            {"target": "BERT", "relation_desc": "相关模型"},
        )
        assert "updated" in result
        # LINK_ONLY 不改正文，只更新 frontmatter 和变更日志
        assert "## 变更日志" in result

    def test_merge_append_related(self, temp_wiki, sample_page):
        merger = ContentMerger(temp_wiki)
        result = merger.merge(
            sample_page,
            "",
            MergeStrategy.APPEND_RELATED,
            {"target": "BERT", "relation_desc": "预训练模型"},
        )
        assert "- [[BERT]] — 预训练模型" in result
        assert "## 变更日志" in result

    def test_merge_append_section(self, temp_wiki, sample_page):
        merger = ContentMerger(temp_wiki)
        result = merger.merge(
            sample_page,
            "最新的研究扩展了 Transformer 到多模态领域。",
            MergeStrategy.APPEND_SECTION,
            {"section_title": "## 最新进展"},
        )
        assert "## 最新进展" in result
        assert "最新的研究扩展了 Transformer 到多模态领域。" in result

    def test_merge_rebuilds_frontmatter(self, temp_wiki, sample_page):
        merger = ContentMerger(temp_wiki)
        result = merger.merge(
            sample_page,
            "",
            MergeStrategy.LINK_ONLY,
        )
        assert result.startswith("---")
        assert 'updated: "' in result

    def test_heading_level(self, temp_wiki):
        merger = ContentMerger(temp_wiki)
        assert merger._heading_level("# Title") == 1
        assert merger._heading_level("## Section") == 2
        assert merger._heading_level("### Subsection") == 3
        assert merger._heading_level("Not a title") == 0
        assert merger._heading_level("#NotTitle") == 0  # 没有空格


class TestSafeWriter:
    """测试 SafeWriter 安全写入功能"""

    @pytest.fixture
    def temp_wiki(self, tmp_path):
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        return WikiManager(wiki_dir)

    @pytest.fixture
    def sample_page(self, temp_wiki):
        content = "# TestPage\n\n原始内容。\n\n## 变更日志\n\n- 2026-04-10: 初始创建\n"
        temp_wiki.create_page(
            "TestPage",
            content,
            {"created": "2026-04-10", "updated": "2026-04-10", "status": "active"},
        )
        return temp_wiki.get_page("TestPage")

    def test_prepare(self, temp_wiki, sample_page):
        writer = SafeWriter(temp_wiki)
        merger = ContentMerger(temp_wiki)
        new_content = merger.merge(
            sample_page,
            "",
            MergeStrategy.APPEND_RELATED,
            {"target": "Other", "relation_desc": "相关"},
        )
        proposal = writer.prepare(
            sample_page,
            new_content,
            reason="添加关联",
            strategy=MergeStrategy.APPEND_RELATED,
        )
        assert isinstance(proposal, ChangeProposal)
        assert proposal.page_title == "TestPage"
        assert "---" in proposal.diff

    def test_apply(self, temp_wiki, sample_page):
        writer = SafeWriter(temp_wiki)
        merger = ContentMerger(temp_wiki)
        new_content = merger.merge(
            sample_page,
            "",
            MergeStrategy.APPEND_RELATED,
            {"target": "Other", "relation_desc": "相关"},
        )
        proposal = writer.prepare(
            sample_page,
            new_content,
            reason="添加关联",
            strategy=MergeStrategy.APPEND_RELATED,
        )
        backup = writer.apply(proposal)

        # 验证备份存在
        assert backup.exists()
        # 验证页面已更新
        updated_page = temp_wiki.get_page("TestPage")
        assert "[[Other]]" in updated_page.content

    def test_rollback(self, temp_wiki, sample_page):
        writer = SafeWriter(temp_wiki)
        merger = ContentMerger(temp_wiki)
        original_content = sample_page.path.read_text(encoding="utf-8")

        new_content = merger.merge(
            sample_page,
            "",
            MergeStrategy.APPEND_RELATED,
            {"target": "Other", "relation_desc": "相关"},
        )
        proposal = writer.prepare(
            sample_page,
            new_content,
            reason="添加关联",
            strategy=MergeStrategy.APPEND_RELATED,
        )
        writer.apply(proposal)

        # 回滚
        result = writer.rollback(sample_page.path)
        assert result is True

        # 验证恢复原始内容
        restored = temp_wiki.get_page("TestPage")
        assert restored.path.read_text(encoding="utf-8") == original_content

    def test_rollback_no_backup(self, temp_wiki, sample_page):
        writer = SafeWriter(temp_wiki)
        result = writer.rollback(sample_page.path)
        assert result is False

    def test_list_backups(self, temp_wiki, sample_page):
        writer = SafeWriter(temp_wiki)
        merger = ContentMerger(temp_wiki)

        new_content = merger.merge(
            sample_page,
            "",
            MergeStrategy.APPEND_RELATED,
            {"target": "Other", "relation_desc": "相关"},
        )
        proposal = writer.prepare(
            sample_page,
            new_content,
            reason="添加关联",
            strategy=MergeStrategy.APPEND_RELATED,
        )
        writer.apply(proposal)

        backups = writer.list_backups(sample_page.path)
        assert len(backups) == 1
        assert backups[0].name.endswith("TestPage.md")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
