#!/usr/bin/env python3
"""jsondiff — structurally diff two JSON files.

Usage:
    python jsondiff.py old.json new.json
    python jsondiff.py old.json new.json --ignore updated_at,version
    python jsondiff.py old.json new.json --json
    python jsondiff.py old.json new.json --brief

Exit codes: 0 = identical, 1 = differences found, 2 = error.
"""

import argparse
import json
import sys

VERSION = "1.0.0"


class DiffEntry:
    """A single difference between two JSON documents."""

    def __init__(self, kind, path, old=None, new=None):
        self.kind = kind          # "added" | "removed" | "changed"
        self.path = path          # JSON-Pointer-ish path, e.g. users[2].email
        self.old = old
        self.new = new

    def to_dict(self):
        return {
            "type": self.kind,
            "path": self.path,
            "old": self.old,
            "new": self.new,
        }

    def __repr__(self):
        if self.kind == "added":
            return f"{self.path}: <added> {format_value(self.new)}"
        if self.kind == "removed":
            return f"{self.path}: {format_value(self.old)} <removed>"
        return f"{self.path}: {format_value(self.old)} -> {format_value(self.new)}"


def format_value(value):
    """Render a scalar (or small composite) for human-readable output."""
    if isinstance(value, str):
        return json.dumps(value)
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def join_path(base, key):
    """Append an object key to a path (dot notation, root is empty)."""
    if not base:
        return str(key)
    return f"{base}.{key}"


def join_index(base, index):
    """Append an array index to a path (bracket notation)."""
    return f"{base}[{index}]"


def _is_ignored(key, ignore):
    return key in ignore


def diff_values(old, new, path, ignore, out):
    """Recursively diff two JSON values, appending DiffEntry items to out."""
    if isinstance(old, dict) and isinstance(new, dict):
        for key in old:
            if _is_ignored(key, ignore):
                continue
            if key not in new:
                out.append(DiffEntry("removed", join_path(path, key), old=old[key]))
        for key in new:
            if _is_ignored(key, ignore):
                continue
            if key not in old:
                out.append(DiffEntry("added", join_path(path, key), new=new[key]))
            else:
                diff_values(old[key], new[key], join_path(path, key), ignore, out)
        return

    if isinstance(old, list) and isinstance(new, list):
        shared = min(len(old), len(new))
        for i in range(shared):
            diff_values(old[i], new[i], join_index(path, i), ignore, out)
        for i in range(shared, len(old)):
            out.append(DiffEntry("removed", join_index(path, i), old=old[i]))
        for i in range(shared, len(new)):
            out.append(DiffEntry("added", join_index(path, i), new=new[i]))
        return

    if type(old) is not type(new) or old != new:
        out.append(DiffEntry("changed", path or "$", old=old, new=new))


def diff_documents(old_doc, new_doc, ignore=None):
    """Return a list of DiffEntry items between two parsed JSON documents."""
    ignore = set(ignore or [])
    entries = []
    diff_values(old_doc, new_doc, "", ignore, entries)
    return entries


def load_json(path):
    """Load a JSON file, raising a friendly error on failure."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        raise SystemExit(f"jsondiff: error: file not found: {path}")
    except IsADirectoryError:
        raise SystemExit(f"jsondiff: error: not a file: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"jsondiff: error: invalid JSON in {path}: {exc.msg} "
            f"(line {exc.lineno}, column {exc.colno})"
        )
    except OSError as exc:
        raise SystemExit(f"jsondiff: error: cannot read {path}: {exc.strerror}")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="jsondiff",
        description="Structurally diff two JSON files.",
    )
    parser.add_argument("old", help="path to the first (old) JSON file")
    parser.add_argument("new", help="path to the second (new) JSON file")
    parser.add_argument(
        "--ignore",
        metavar="KEYS",
        default="",
        help="comma-separated keys to skip at any depth, e.g. --ignore updated_at,version",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of human-readable lines",
    )
    parser.add_argument(
        "--brief",
        action="store_true",
        help="print only a count summary of the differences",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    ignore = {key.strip() for key in args.ignore.split(",") if key.strip()}

    try:
        old_doc = load_json(args.old)
        new_doc = load_json(args.new)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2

    entries = diff_documents(old_doc, new_doc, ignore)

    if args.json:
        payload = {
            "identical": not entries,
            "differences": len(entries),
            "added": sum(1 for e in entries if e.kind == "added"),
            "removed": sum(1 for e in entries if e.kind == "removed"),
            "changed": sum(1 for e in entries if e.kind == "changed"),
            "entries": [e.to_dict() for e in entries],
        }
        print(json.dumps(payload, indent=2))
    elif args.brief:
        if not entries:
            print("Files are identical.")
        else:
            added = sum(1 for e in entries if e.kind == "added")
            removed = sum(1 for e in entries if e.kind == "removed")
            changed = sum(1 for e in entries if e.kind == "changed")
            print(
                f"{len(entries)} difference(s): "
                f"{added} added, {removed} removed, {changed} changed."
            )
    else:
        if not entries:
            print("Files are identical.")
        else:
            for entry in entries:
                print(entry)

    return 0 if not entries else 1


if __name__ == "__main__":
    sys.exit(main())
