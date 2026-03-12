#!/usr/bin/env python3
"""
Idempotently add or replace the '## License' section in README.md
Usage: python update_readme_license.py
"""
import re
from pathlib import Path
readme = Path("README.md")
snippet = (
    "## License\n\n"
    "This repository is licensed under the MIT License — see the [LICENSE](./LICENSE) file.\n\n"
    "Proprietary components (if any) are described in [LICENSE_PROPRIETARY.txt](./LICENSE_PROPRIETARY.txt).\n"
)
if not readme.exists():
    readme.write_text(snippet, encoding="utf-8")
    print("Created README.md with License section.")
    raise SystemExit(0)

text = readme.read_text(encoding="utf-8")
if snippet in text:
    print("README.md already contains the exact License snippet. No changes made.")
    raise SystemExit(0)

if "## License" in text:
    # replace from '## License' to next top-level header '## ' or EOF
    new_text = re.sub(r"## License.*?(?=\n## |\Z)", snippet + "\n", text, flags=re.S)
    readme.write_text(new_text, encoding="utf-8")
    print("Replaced existing '## License' section in README.md.")
else:
    # append (ensure file ends with newline)
    if not text.endswith("\n"):
        text += "\n"
    text += "\n" + snippet + "\n"
    readme.write_text(text, encoding="utf-8")
    print("Appended '## License' section to README.md.")
