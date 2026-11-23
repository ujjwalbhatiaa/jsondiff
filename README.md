# jsondiff

A dependency-free Python CLI that structurally diffs two JSON files.

Give it two JSON documents and it prints every difference as a readable
path — added keys, removed keys, and changed values — with JSON-Pointer-ish
paths like `users[2].email`.

## Why

`diff` compares text line by line, so a reordered key or a re-indented file
looks like a wall of changes. `jsondiff` parses both files and compares
their structure, so it reports only what actually changed, no matter how
the files are formatted.

## Requirements

- Python 3.8 or newer
- No third-party dependencies — standard library only

## Usage

```sh
python jsondiff.py old.json new.json
python jsondiff.py old.json new.json --ignore updated_at,version
python jsondiff.py old.json new.json --json
python jsondiff.py old.json new.json --brief
```

### Example

`old.json`:

```json
{
  "name": "api",
  "version": 1,
  "users": [
    {"id": 1, "email": "ana@example.com"},
    {"id": 2, "email": "ben@example.com"}
  ]
}
```

`new.json`:

```json
{
  "name": "api",
  "version": 2,
  "users": [
    {"id": 1, "email": "ana@example.com"},
    {"id": 2, "email": "ben@newmail.com"}
  ],
  "debug": true
}
```

```sh
$ python jsondiff.py old.json new.json
version: 1 -> 2
users[1].email: "ben@example.com" -> "ben@newmail.com"
debug: <added> true
```

Ignore volatile keys (timestamps, versions) at any depth:

```sh
$ python jsondiff.py old.json new.json --ignore version
users[1].email: "ben@example.com" -> "ben@newmail.com"
debug: <added> true
```

Machine-readable output for scripts and CI:

```sh
$ python jsondiff.py old.json new.json --json
{
  "identical": false,
  "differences": 3,
  "added": 1,
  "removed": 0,
  "changed": 2,
  "entries": [
    {"type": "changed", "path": "version", "old": 1, "new": 2},
    {"type": "changed", "path": "users[1].email",
     "old": "ben@example.com", "new": "ben@newmail.com"},
    {"type": "added", "path": "debug", "old": null, "new": true}
  ]
}
```

Counts only:

```sh
$ python jsondiff.py old.json new.json --brief
3 difference(s): 1 added, 0 removed, 2 changed.
```

## Exit codes

| Code | Meaning |
| ---- | ------- |
| 0 | Files are identical |
| 1 | Differences found |
| 2 | Error (missing file, invalid JSON, bad usage) |

Exit code 1 makes `jsondiff` easy to use in CI: fail the build when a
config file drifted from its expected shape.

## How differences are reported

- **Objects** are compared key by key; missing keys are `added`/`removed`,
  present keys are compared recursively.
- **Arrays** are compared element by element, by index; extra elements at
  the end are `added`/`removed`. (Reordering an array therefore shows up
  as per-index changes — this is a structural diff, not a sequence diff.)
- **Type changes** (a number becoming a string, an object becoming a list)
  are reported as `changed`, including JSON `true` vs `1`, which are
  different values even though Python's `True == 1`.
- Paths use dot notation for object keys (`user.email`) and brackets for
  array indices (`users[2].email`). A changed top-level scalar is reported
  at the root path `$`.

## Running the tests

```sh
python -m pytest tests/ -v
```

## License

MIT — see [LICENSE](LICENSE).
