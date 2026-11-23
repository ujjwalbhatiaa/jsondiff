"""Tests for jsondiff."""

import json
import subprocess
import sys

import pytest

from jsondiff import DiffEntry, diff_documents, diff_values, format_value, main


def kinds(entries):
    return [(e.kind, e.path) for e in entries]


# --- core diffing: identical documents -------------------------------------


def test_identical_scalars():
    assert diff_documents(1, 1) == []
    assert diff_documents("a", "a") == []
    assert diff_documents(None, None) == []
    assert diff_documents(True, True) == []


def test_identical_nested():
    doc = {"a": [1, 2, {"b": "x"}], "c": None}
    assert diff_documents(doc, doc) == []


def test_identical_empty_containers():
    assert diff_documents({}, {}) == []
    assert diff_documents([], []) == []


# --- scalars and type changes ----------------------------------------------


def test_changed_scalar():
    entries = diff_documents(1, 2)
    assert len(entries) == 1
    assert entries[0].kind == "changed"
    assert entries[0].path == "$"
    assert entries[0].old == 1 and entries[0].new == 2


def test_type_change_number_to_string():
    entries = diff_documents({"port": 8080}, {"port": "8080"})
    assert entries[0].kind == "changed"
    assert entries[0].path == "port"


def test_type_change_bool_vs_int():
    # In Python True == 1, but JSON true and 1 are different types.
    entries = diff_documents({"flag": True}, {"flag": 1})
    assert len(entries) == 1
    assert entries[0].kind == "changed"


def test_type_change_object_to_list():
    entries = diff_documents({"x": {"a": 1}}, {"x": [1]})
    assert entries[0].kind == "changed"
    assert entries[0].path == "x"


def test_null_to_value():
    entries = diff_documents({"x": None}, {"x": "set"})
    assert entries[0].kind == "changed"
    assert entries[0].old is None and entries[0].new == "set"


# --- objects -----------------------------------------------------------------


def test_added_key():
    entries = diff_documents({"a": 1}, {"a": 1, "b": 2})
    assert kinds(entries) == [("added", "b")]
    assert entries[0].new == 2


def test_removed_key():
    entries = diff_documents({"a": 1, "b": 2}, {"a": 1})
    assert kinds(entries) == [("removed", "b")]
    assert entries[0].old == 2


def test_nested_object_path():
    entries = diff_documents(
        {"user": {"email": "a@example.com"}},
        {"user": {"email": "b@example.com"}},
    )
    assert kinds(entries) == [("changed", "user.email")]
    assert entries[0].old == "a@example.com"
    assert entries[0].new == "b@example.com"


def test_deeply_nested_path():
    entries = diff_documents(
        {"a": {"b": {"c": {"d": 1}}}},
        {"a": {"b": {"c": {"d": 2}}}},
    )
    assert kinds(entries) == [("changed", "a.b.c.d")]


# --- arrays ------------------------------------------------------------------


def test_array_element_changed():
    entries = diff_documents(
        {"users": [{"email": "a"}, {"email": "b"}]},
        {"users": [{"email": "a"}, {"email": "c"}]},
    )
    assert kinds(entries) == [("changed", "users[1].email")]


def test_array_appended():
    entries = diff_documents([1, 2], [1, 2, 3])
    assert kinds(entries) == [("added", "[2]")]


def test_array_truncated():
    entries = diff_documents([1, 2, 3], [1])
    assert kinds(entries) == [("removed", "[1]"), ("removed", "[2]")]


def test_array_of_objects_index_path():
    entries = diff_documents(
        {"users": [{"id": 1}, {"id": 2}]},
        {"users": [{"id": 1}, {"id": 3}]},
    )
    assert kinds(entries) == [("changed", "users[1].id")]


# --- --ignore ----------------------------------------------------------------


def test_ignore_key_at_any_depth():
    old = {"updated_at": "t1", "nested": {"updated_at": "t1", "v": 1}}
    new = {"updated_at": "t2", "nested": {"updated_at": "t2", "v": 2}}
    entries = diff_documents(old, new, ignore={"updated_at"})
    assert kinds(entries) == [("changed", "nested.v")]


def test_ignore_multiple_keys():
    old = {"version": 1, "ts": 10, "keep": 1}
    new = {"version": 2, "ts": 20, "keep": 2}
    entries = diff_documents(old, new, ignore={"version", "ts"})
    assert kinds(entries) == [("changed", "keep")]


def test_ignore_does_not_hide_other_changes():
    old = {"ignore_me": 1, "a": 1}
    new = {"ignore_me": 99, "a": 2}
    entries = diff_documents(old, new, ignore={"ignore_me"})
    assert kinds(entries) == [("changed", "a")]


# --- formatting --------------------------------------------------------------


def test_format_value():
    assert format_value("hi") == '"hi"'
    assert format_value(None) == "null"
    assert format_value(True) == "true"
    assert format_value(False) == "false"
    assert format_value(42) == "42"
    assert format_value([1, 2]) == "[1, 2]"


def test_entry_repr_changed():
    entry = DiffEntry("changed", "users[2].email", old="a", new="b")
    assert repr(entry) == 'users[2].email: "a" -> "b"'


def test_entry_repr_added_removed():
    assert repr(DiffEntry("added", "x", new=5)) == "x: <added> 5"
    assert repr(DiffEntry("removed", "x", old=5)) == "x: 5 <removed>"


def test_entry_to_dict():
    entry = DiffEntry("changed", "a", old=1, new=2)
    assert entry.to_dict() == {"type": "changed", "path": "a", "old": 1, "new": 2}


# --- CLI: exit codes and output modes ---------------------------------------


def run_cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, "jsondiff.py", *args],
        capture_output=True,
        text=True,
        cwd=cwd or str(__file__.rsplit("/", 2)[0]),
    )


def write(tmp_path, name, doc):
    path = tmp_path / name
    path.write_text(json.dumps(doc))
    return str(path)


def test_cli_identical_exit_0(tmp_path):
    old = write(tmp_path, "old.json", {"a": 1})
    new = write(tmp_path, "new.json", {"a": 1})
    result = run_cli(old, new)
    assert result.returncode == 0
    assert "identical" in result.stdout.lower()


def test_cli_differences_exit_1(tmp_path):
    old = write(tmp_path, "old.json", {"a": 1, "b": 2})
    new = write(tmp_path, "new.json", {"a": 1, "b": 3, "c": 4})
    result = run_cli(old, new)
    assert result.returncode == 1
    assert "b: 2 -> 3" in result.stdout
    assert "c: <added> 4" in result.stdout


def test_cli_json_mode(tmp_path):
    old = write(tmp_path, "old.json", {"a": 1})
    new = write(tmp_path, "new.json", {"a": 2})
    result = run_cli(old, new, "--json")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["identical"] is False
    assert payload["differences"] == 1
    assert payload["changed"] == 1
    assert payload["entries"][0] == {
        "type": "changed",
        "path": "a",
        "old": 1,
        "new": 2,
    }


def test_cli_json_mode_identical(tmp_path):
    old = write(tmp_path, "old.json", {"a": 1})
    new = write(tmp_path, "new.json", {"a": 1})
    result = run_cli(old, new, "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["identical"] is True
    assert payload["entries"] == []


def test_cli_brief_mode(tmp_path):
    old = write(tmp_path, "old.json", {"a": 1, "b": 2})
    new = write(tmp_path, "new.json", {"a": 9, "c": 3})
    result = run_cli(old, new, "--brief")
    assert result.returncode == 1
    assert "3 difference(s): 1 added, 1 removed, 1 changed." in result.stdout


def test_cli_ignore_flag(tmp_path):
    old = write(tmp_path, "old.json", {"v": 1, "ts": 1})
    new = write(tmp_path, "new.json", {"v": 1, "ts": 2})
    result = run_cli(old, new, "--ignore", "ts")
    assert result.returncode == 0


def test_cli_missing_file_exit_2(tmp_path):
    result = run_cli(str(tmp_path / "nope.json"), str(tmp_path / "also-nope.json"))
    assert result.returncode == 2
    assert "not found" in result.stderr


def test_cli_invalid_json_exit_2(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    good = write(tmp_path, "good.json", {"a": 1})
    result = run_cli(str(bad), good)
    assert result.returncode == 2
    assert "invalid JSON" in result.stderr


def test_main_returns_exit_codes(tmp_path):
    old = write(tmp_path, "old.json", {"a": 1})
    new = write(tmp_path, "new.json", {"a": 1})
    assert main([old, new]) == 0
    new2 = write(tmp_path, "new2.json", {"a": 2})
    assert main([old, new2]) == 1
    assert main([str(tmp_path / "missing.json"), new]) == 2
