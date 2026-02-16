import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

ROOTS = [
    os.path.join(ROOT, "apps", "backend"),
    os.path.join(ROOT, "apps", "iframe-vue"),
    os.path.join(ROOT, "scripts"),
]

TEXT_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".css", ".scss", ".sass",
    ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".ini", ".env",
    ".sql", ".html", ".htm", ".sh", ".ps1",
}

IGNORE_DIRS = {
    "node_modules", "dist", "build", ".git", ".venv", "venv", "__pycache__",
}

BAD_SEQ = ["???", "�"]

SUPPLEMENT_RANGES = [
    (0x0400, 0x040F),
    (0x0450, 0x045F),
]

SUPPLEMENT_ALLOW = {0x0401, 0x0451}  # Ё/ё allowed


def is_text_file(path: str) -> bool:
    _, ext = os.path.splitext(path)
    return ext.lower() in TEXT_EXTS


def has_bad_sequences(text: str) -> bool:
    for s in BAD_SEQ:
        if s in text:
            return True
    for ch in text:
        code = ord(ch)
        for a, b in SUPPLEMENT_RANGES:
            if a <= code <= b and code not in SUPPLEMENT_ALLOW:
                return True
    return False


def scan_file(path: str, errors: list[str]) -> None:
    if os.path.abspath(path) == os.path.abspath(__file__):
        return
    try:
        with open(path, "rb") as f:
            data = f.read()
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        errors.append(f"NOT_UTF8: {path}")
        return
    except Exception as exc:
        errors.append(f"READ_ERROR: {path} ({exc})")
        return

    if has_bad_sequences(text):
        errors.append(f"MOJIBAKE: {path}")


def walk() -> list[str]:
    errors: list[str] = []
    for root in ROOTS:
        if not os.path.exists(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
            for name in filenames:
                path = os.path.join(dirpath, name)
                if not is_text_file(path):
                    continue
                scan_file(path, errors)
    return errors


def main() -> int:
    errors = walk()
    if errors:
        print("Text integrity check failed:")
        for e in errors:
            print(f"- {e}")
        print("Fix mojibake / encoding issues before commit/deploy.")
        return 1
    print("Text integrity check OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
