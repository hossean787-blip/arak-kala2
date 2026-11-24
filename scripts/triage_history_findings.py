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
    "CHANGE_ME", "CHANGE_THIS", "CHANGE_THIS_TOKEN", "CHANGE_ME_TOKEN",
    "CHANGE_ME_ADMIN_TOKEN", "CHANGE_THIS_ADMIN_TOKEN", "REPLACE_WITH_STRONG_TOKEN",
    "REPLACE_WITH_A_STRONG_TOKEN", "YOUR_STRONG_TOKEN", "YOUR_ADMIN_SECRET",
    "YOUR_API_KEY_HERE", "YOUR_ADMIN_API_KEY_HERE", "YOUR_SECRET",
    "YOUR_ADMIN_SECRET_KEY", "YOUR_ADMIN_KEY_HERE", "YOUR_API_SECRET",
    "CHANGE_THIS_SECRET", "CHANGE_ME_SECRET", "CHANGE_ME_NOW",
    "DEMO_TOKEN", "DEMO_ADMIN_TOKEN", "EXAMPLE_TOKEN", "EXAMPLE_ADMIN_TOKEN",
    "TEST_TOKEN", "TEST_ADMIN_TOKEN", "SAMPLE_TOKEN", "SAMPLE_ADMIN_TOKEN",
    "REPLACE_WITH_YOUR_ADMIN_TOKEN", "YOUR_LONG_RANDOM_TOKEN",
    "YOUR_LONG_RANDOM_ADMIN_TOKEN", "CHANGE_THIS_TO_A_LONG_RANDOM_TOKEN",
}


def source_text(root, rel):
    if "!" in rel:
        outer, inner = rel.split("!", 1)
        with ZipFile(root / outer) as archive:
            return archive.read(inner).decode("utf-8")
    return (root / rel).read_text(encoding="utf-8")


TEST_LINE = 'password = "' + '-'.join(('fresh', 'unique', 'test', 'passphrase', '43')) + '"'
SELF_PATH = 'scripts/triage_history_findings.py'


def reviewed_example(rule, rel, line, text):
    lines = text.splitlines()
    if not 1 <= line <= len(lines):
        return False
    value = lines[line - 1]
    if rule == "generic-api-key" and rel in TEST_PATHS and line == 12:
        return (
            value.strip() == TEST_LINE
            and "class StoreWorkflowTests(TestCase):" in text
            and "create_user(" in text
        )
    if rule == "generic-api-key" and rel == SELF_PATH and line == 44:
        return (
            value.strip() == "value.strip() == " + repr(TEST_LINE)
            and "class StoreWorkflowTests(TestCase):" in text
            and "Never display matched line" in text
        )
    if rule == "curl-auth-header" and rel in README_PATHS and line == 54:
        # A curl command may continue onto subsequent lines. Check only quoted
        # auth headers in the reported command, never print their values.
        context = "\n".join(lines[max(0, line - 2):line + 5])
        headers = re.findall(r"""(?:-H|--header)\s*=?\s*["']((?:Authorization|X-[\w-]+|Api-Key|Api-Token|Key|Token):\s*[^"']+)["']""", context, re.I)
        if len(headers) == 1:
            name, token = headers[0].split(":", 1)
            token = re.sub(r"^\s*(?:Bearer|Basic|(?:Api-)?Token)\s+", "", token, flags=re.I).strip()
            normalized = token.strip("<>{}$").replace("-", "_").upper()
            if normalized in PLACEHOLDERS:
                return True
            print(f"Header classification only: name={name.lower()} length={len(token)} "
                  f"placeholder_like={bool(re.fullmatch(r'(?:YOUR|CHANGE|REPLACE|DEMO|TEST|EXAMPLE|SAMPLE|PUT|INSERT)[_-][A-Za-z0-9_-]+', token, re.I))}")
        else:
            print(f"Header classification only: quoted_header_count={len(headers)}")
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
        if rel in TEST_PATHS | README_PATHS | {SELF_PATH}:
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
