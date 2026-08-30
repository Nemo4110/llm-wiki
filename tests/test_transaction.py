"""
Tests for transaction.py - atomic multi-file write bundles
"""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from llm_wiki.transaction import FileOp, Transaction, TransactionError


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TestTransactionApply:
    """事务应用的成功路径"""

    @pytest.fixture
    def root(self, tmp_path):
        """模拟项目根:wiki/ 目录与根级 log.md"""
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "index.md").write_text("# Index\n\n- [[Old]]\n", encoding="utf-8")
        (tmp_path / "log.md").write_text("# Log\n", encoding="utf-8")
        return tmp_path

    def test_apply_writes_all_ops(self, root):
        tx = Transaction(root)
        tx.stage(
            FileOp(
                op="create",
                path=Path("wiki/NewPage.md"),
                content="---\n---\n\n# NewPage\n",
            )
        )
        tx.stage(
            FileOp(
                op="update",
                path=Path("wiki/index.md"),
                content="# Index\n\n- [[Old]]\n- [[NewPage]]\n",
                expected_sha256=_sha("# Index\n\n- [[Old]]\n"),
            )
        )
        tx.stage(
            FileOp(
                op="update",
                path=Path("log.md"),
                content="# Log\n\n## [2026-08-24] ingest | NewPage\n",
                expected_sha256=_sha("# Log\n"),
            )
        )

        receipt = tx.apply()

        assert (root / "wiki" / "NewPage.md").read_text(
            encoding="utf-8"
        ) == "---\n---\n\n# NewPage\n"
        assert (root / "wiki" / "index.md").read_text(
            encoding="utf-8"
        ) == "# Index\n\n- [[Old]]\n- [[NewPage]]\n"
        assert (root / "log.md").read_text(
            encoding="utf-8"
        ) == "# Log\n\n## [2026-08-24] ingest | NewPage\n"
        assert receipt.changed == [
            Path("wiki/NewPage.md"),
            Path("wiki/index.md"),
            Path("log.md"),
        ]


class TestTransactionFailClosed:
    """校验失败时不写入任何文件"""

    @pytest.fixture
    def root(self, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "index.md").write_text("# Index\n", encoding="utf-8")
        return tmp_path

    def test_create_on_existing_file_writes_nothing(self, root):
        tx = Transaction(root)
        tx.stage(FileOp(op="create", path=Path("wiki/index.md"), content="garbage"))
        tx.stage(FileOp(op="create", path=Path("wiki/New.md"), content="new"))

        with pytest.raises(TransactionError, match="already exists"):
            tx.apply()

        assert (root / "wiki" / "index.md").read_text(encoding="utf-8") == "# Index\n"
        assert not (root / "wiki" / "New.md").exists()

    def test_hash_mismatch_writes_nothing(self, root):
        tx = Transaction(root)
        tx.stage(
            FileOp(
                op="update",
                path=Path("wiki/index.md"),
                content="changed",
                expected_sha256=_sha("stale draft base"),
            )
        )
        tx.stage(FileOp(op="create", path=Path("wiki/New.md"), content="new"))

        with pytest.raises(TransactionError, match="Hash mismatch"):
            tx.apply()

        assert (root / "wiki" / "index.md").read_text(encoding="utf-8") == "# Index\n"
        assert not (root / "wiki" / "New.md").exists()

    def test_update_requires_expected_hash(self, root):
        tx = Transaction(root)
        tx.stage(FileOp(op="update", path=Path("wiki/index.md"), content="changed"))

        with pytest.raises(TransactionError, match="expected_sha256"):
            tx.apply()

        assert (root / "wiki" / "index.md").read_text(encoding="utf-8") == "# Index\n"

    def test_update_on_missing_file_fails(self, root):
        tx = Transaction(root)
        tx.stage(
            FileOp(
                op="update",
                path=Path("wiki/Ghost.md"),
                content="x",
                expected_sha256=_sha("x"),
            )
        )

        with pytest.raises(TransactionError, match="does not exist"):
            tx.apply()

    def test_path_escape_rejected(self, root):
        tx = Transaction(root)
        tx.stage(FileOp(op="create", path=Path("../outside.md"), content="x"))

        with pytest.raises(TransactionError, match="escapes"):
            tx.apply()

    def test_duplicate_path_rejected(self, root):
        tx = Transaction(root)
        tx.stage(FileOp(op="create", path=Path("wiki/A.md"), content="1"))
        tx.stage(FileOp(op="create", path=Path("wiki/A.md"), content="2"))

        with pytest.raises(TransactionError, match="Duplicate"):
            tx.apply()

    def test_empty_transaction_rejected(self, root):
        with pytest.raises(TransactionError, match="no staged"):
            Transaction(root).apply()

    def test_unknown_op_rejected_at_stage(self, root):
        with pytest.raises(TransactionError, match="Unknown op"):
            Transaction(root).stage(
                FileOp(op="delete", path=Path("wiki/index.md"), content="")
            )


class TestTransactionRollback:
    """写入中途失败时自动回滚"""

    def test_mid_apply_failure_restores_originals(self, tmp_path, monkeypatch):
        root = tmp_path
        wiki = root / "wiki"
        wiki.mkdir()
        (wiki / "index.md").write_text("# Index\n", encoding="utf-8")
        (root / "log.md").write_text("# Log\n", encoding="utf-8")

        tx = Transaction(root)
        tx.stage(FileOp(op="create", path=Path("wiki/New.md"), content="new"))
        tx.stage(
            FileOp(
                op="update",
                path=Path("wiki/index.md"),
                content="changed",
                expected_sha256=_sha("# Index\n"),
            )
        )
        tx.stage(
            FileOp(
                op="update",
                path=Path("log.md"),
                content="changed",
                expected_sha256=_sha("# Log\n"),
            )
        )

        original_write = Transaction._write
        calls = {"n": 0}

        def fail_on_third(self, op):
            calls["n"] += 1
            if calls["n"] == 3:
                raise OSError("simulated disk failure")
            original_write(self, op)

        monkeypatch.setattr(Transaction, "_write", fail_on_third)

        with pytest.raises(TransactionError, match="rolled back"):
            tx.apply()

        # 已创建的文件被移除,已更新的文件恢复原样
        assert not (wiki / "New.md").exists()
        assert (wiki / "index.md").read_text(encoding="utf-8") == "# Index\n"
        assert (root / "log.md").read_text(encoding="utf-8") == "# Log\n"


class TestTransactionDiff:
    """应用前的 diff 预览(供 --dry-run 审查)"""

    def test_diff_shows_all_staged_changes(self, tmp_path):
        root = tmp_path
        wiki = root / "wiki"
        wiki.mkdir()
        (wiki / "index.md").write_text("# Index\n", encoding="utf-8")

        tx = Transaction(root)
        tx.stage(
            FileOp(op="create", path=Path("wiki/New.md"), content="# New\n\nbody\n")
        )
        tx.stage(
            FileOp(
                op="update",
                path=Path("wiki/index.md"),
                content="# Index\n\n- [[New]]\n",
                expected_sha256=_sha("# Index\n"),
            )
        )

        diff = tx.diff()

        assert "wiki/New.md" in diff
        assert "wiki/index.md" in diff
        assert "+# New" in diff
        assert "+- [[New]]" in diff
        # diff 不写入任何文件
        assert not (wiki / "New.md").exists()
        assert (wiki / "index.md").read_text(encoding="utf-8") == "# Index\n"


class TestLoadBundle:
    """从 YAML manifest 加载事务"""

    def _write_manifest(self, tmp_path, body: str) -> Path:
        manifest = tmp_path / "temp" / "tx-bundle.yaml"
        manifest.parent.mkdir(exist_ok=True)
        manifest.write_text(body, encoding="utf-8")
        return manifest

    def test_loads_ops_with_content_from_files(self, tmp_path):
        root = tmp_path
        (root / "wiki").mkdir()
        (root / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")
        (root / "temp").mkdir()
        (root / "temp" / "draft-index.md").write_text(
            "# Index\n\n- [[New]]\n", encoding="utf-8"
        )
        (root / "temp" / "draft-new.md").write_text("# New\n", encoding="utf-8")

        manifest = self._write_manifest(
            tmp_path,
            f"""
ops:
  - op: create
    path: wiki/New.md
    content_path: {root / "temp" / "draft-new.md"}
  - op: update
    path: wiki/index.md
    content_path: {root / "temp" / "draft-index.md"}
    expected_sha256: "{_sha("# Index\n")}"
""",
        )

        from llm_wiki.transaction import load_bundle

        tx = load_bundle(manifest, root)

        receipt = tx.apply()
        assert len(receipt.changed) == 2
        assert (root / "wiki" / "New.md").read_text(encoding="utf-8") == "# New\n"
        assert (root / "wiki" / "index.md").read_text(
            encoding="utf-8"
        ) == "# Index\n\n- [[New]]\n"

    def test_missing_ops_key_rejected(self, tmp_path):
        from llm_wiki.transaction import load_bundle

        manifest = self._write_manifest(tmp_path, "foo: bar\n")

        with pytest.raises(TransactionError, match="ops"):
            load_bundle(manifest, tmp_path)

    def test_missing_content_file_rejected(self, tmp_path):
        from llm_wiki.transaction import load_bundle

        manifest = self._write_manifest(
            tmp_path,
            """
ops:
  - op: create
    path: wiki/New.md
    content_path: /nonexistent/draft.md
""",
        )

        with pytest.raises(TransactionError, match="content"):
            load_bundle(manifest, tmp_path)

    def test_unknown_op_in_manifest_rejected(self, tmp_path):
        from llm_wiki.transaction import load_bundle

        draft = tmp_path / "draft.md"
        draft.write_text("x", encoding="utf-8")
        manifest = self._write_manifest(
            tmp_path,
            f"""
ops:
  - op: delete
    path: wiki/index.md
    content_path: {draft}
""",
        )

        with pytest.raises(TransactionError, match="Unknown op"):
            load_bundle(manifest, tmp_path)


class TestTransactionCheck:
    """dry-run 软校验:逐项报告状态与当前哈希,不抛出、不写入"""

    def test_check_reports_status_per_op(self, tmp_path):
        root = tmp_path
        wiki = root / "wiki"
        wiki.mkdir()
        (wiki / "index.md").write_text("# Index\n", encoding="utf-8")

        tx = Transaction(root)
        tx.stage(FileOp(op="create", path=Path("wiki/New.md"), content="new"))
        tx.stage(FileOp(op="create", path=Path("wiki/index.md"), content="dup"))
        tx.stage(
            FileOp(op="update", path=Path("wiki/index.md"), content="changed")
        )  # 未提供 expected_sha256
        tx.stage(
            FileOp(
                op="update",
                path=Path("wiki/Ghost.md"),
                content="x",
                expected_sha256=_sha("x"),
            )
        )

        checks = tx.check()

        assert [c.ok for c in checks] == [True, False, True, False]
        assert checks[0].detail == "new file"
        assert "already exists" in checks[1].detail
        assert _sha("# Index\n") in checks[2].detail  # 给出当前哈希供回填
        assert "does not exist" in checks[3].detail
        # 不产生任何写入
        assert not (wiki / "New.md").exists()


class TestManifestHashQuoting:
    """回归:YAML 会把未加引号的全数字哈希解析成整数,必须拒绝"""

    def test_unquoted_numeric_hash_rejected(self, tmp_path):
        from llm_wiki.transaction import load_bundle

        draft = tmp_path / "draft.md"
        draft.write_text("x", encoding="utf-8")
        (tmp_path / "wiki").mkdir()
        (tmp_path / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")
        manifest = tmp_path / "bundle.yaml"
        manifest.write_text(
            f"""
ops:
  - op: update
    path: wiki/index.md
    content_path: {draft}
    expected_sha256: {"0" * 64}
""",
            encoding="utf-8",
        )

        with pytest.raises(TransactionError, match="quoted string"):
            load_bundle(manifest, tmp_path)
