"""Fail closed on history scan results except precisely verified non-production examples."""
import json
import re
import sys
from pathlib import Path
from zipfile import ZipFile

TEST_PATHS = {
    "backend/store/tests.py",
    "archives/arak-kala/Arak-Kala-Web-Prototype.zip!Arak-Kala-Web/store/tests.py",
}
README_PATHS = {
    "archives/arak-kala/ArakKala_Download.zip!arak_kala_custom_store/README.md",
    "archives/arak-kala/arak_kala_custom_store.zip!arak_kala_custom_store/README.md",
    "archives/arak-kala/ArakKala_Visual_Complete.zip!ArakKala/README.md",
    "archives/arak-kala/ArakKala_Pro_v1.zip!ArakKala_Pro_v1/README.md",
}
# A literal documentation placeholder, not any arbitrary credential.
PLACEHOLDERS = {
    "YOUR_ADMIN_TOKEN", "YOUR_TOKEN", "YOUR_API_TOKEN", "YOUR_API_KEY",
    "YOUR_ADMIN_API_KEY", "YOUR_ADMIN_KEY", "YOUR_SECRET_TOKEN",
    "YOUR_SECRET_KEY", "YOUR_ACCESS_TOKEN", "YOUR_BEARER_TOKEN",
    "YOUR_TOKEN_HERE", "YOUR_ADMIN_TOKEN_HERE", "REPLACE_ME",
    "REPLACE_WITH_ADMIN_TOKEN", "REPLACE_WITH_YOUR_TOKEN",
    "ADMIN_TOKEN", "API_TOKEN", "TOKEN",
}


def source_text(root, rel):
    if "!" in rel:
        outer, inner = rel.split("!", 1)
        with ZipFile(root / outer) as archive:
            return archive.read(inner).decode("utf-8")
    return (root / rel).read_text(encoding="utf-8")


def reviewed_example(rule, rel, line, text):
    lines = text.splitlines()
    if not 1 <= line <= len(lines):
        return False
    value = lines[line - 1]
    if rule == "generic-api-key" and rel in TEST_PATHS and line == 12:
        return (
            value.strip() == 'password = "fresh-unique-test-passphrase-43"'
            and "class StoreWorkflowTests(TestCase):" in text
            and "create_user(" in text
        )
    if rule == "curl-auth-header" and rel in README_PATHS and line == 54:
        match = re.search(r"Authorization:\s*Bearer\s+([^\"'\s]+)", value, re.I)
        if match:
            token = match.group(1).strip("<>{}$").replace("-", "_").upper()
            return token in PLACEHOLDERS
    return False


def main():
    root = Path(sys.argv[1]).resolve()
    report = Path(sys.argv[2])
    findings = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(findings, list) or not findings:
        raise SystemExit("Scanner returned findings status without a valid nonempty report.")
    unknown = 0
    for item in findings:
        path = str(item["File"])
        prefix = str(root) + "/"
        rel = path[len(prefix):] if path.startswith(prefix) else path
        rule = str(item["RuleID"])
        line = int(item["StartLine"])
        verified = False
        if rel in TEST_PATHS | README_PATHS:
            try:
                verified = reviewed_example(rule, rel, line, source_text(root, rel))
            except (OSError, KeyError, UnicodeError, ValueError):
                verified = False
        if not verified:
            unknown += 1
        # Never display matched line, match or credential value.
        print(f"{'Verified example' if verified else 'UNRESOLVED'}: {rule} {rel} line {line}")
    print(f"Reviewed {len(findings)} findings; unresolved: {unknown}")
    return int(unknown > 0)


if __name__ == "__main__":
    raise SystemExit(main())
