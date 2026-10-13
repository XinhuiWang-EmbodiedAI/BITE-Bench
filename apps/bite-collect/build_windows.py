"""Build an offline Windows x64 ZIP from a hash-verified official runtime.

No network request, installer, PATH change or user data is included.
"""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME_URL = "https://www.python.org/ftp/python/3.14.7/python-3.14.7-embed-amd64.zip"
RUNTIME_SHA256 = "d297e5ff019966817ad8502465176139f2d3d840fa4ed84b13bed399a6ab1f15"
SOURCE_URL = "https://www.python.org/downloads/release/python-3147/"


def build(runtime, target):
    if hashlib.sha256(runtime.read_bytes()).hexdigest() != RUNTIME_SHA256:
        raise ValueError("Official Python runtime SHA256 mismatch")
    target.parent.mkdir(parents=True, exist_ok=True)
    sources = []
    for folder in ["bite_collect", "static", "fixtures/synthetic", "tests"]:
        sources.extend(
            p
            for p in (ROOT / folder).rglob("*")
            if p.is_file() and p.suffix in {".py", ".html", ".css", ".js", ".json"}
        )
    sources.extend(
        ROOT / f
        for f in [
            "run.py",
            "start-windows.cmd",
            "README.md",
            "QUESTIONNAIRE_CONTRACT.md",
        ]
    )
    with (
        target.open("xb") as output,
        zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive,
    ):
        for p in sorted(sources):
            archive.write(p, p.relative_to(ROOT))
        with zipfile.ZipFile(runtime) as python_zip:
            for name in python_zip.namelist():
                if (
                    name.endswith("/")
                    or name.startswith("/")
                    or ".." in Path(name).parts
                ):
                    raise ValueError("Unsafe runtime archive member")
                content = python_zip.read(name)
                if name == "python314._pth":
                    # Isolated interpreter may import only stdlib/runtime and app root.
                    content = b"python314.zip\n.\n..\n"
                archive.writestr("runtime-python/" + name, content)
        archive.writestr(
            "runtime-python/PROVENANCE.json",
            json.dumps(
                {
                    "version": "3.14.7",
                    "url": RUNTIME_URL,
                    "source": SOURCE_URL,
                    "sha256": RUNTIME_SHA256,
                    "modified_file": "python314._pth",
                    "modification": "add parent app directory to isolated module path",
                },
                indent=2,
            ),
        )
    return hashlib.sha256(target.read_bytes()).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-zip", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(build(args.runtime_zip, args.out))
