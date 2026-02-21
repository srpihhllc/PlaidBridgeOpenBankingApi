# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/fix_cascades.py

import os
import re

MODELS_DIR = "/home/srpihhllc/PlaidBridgeOpenBankingApi/app/models/"

# Regex to find ForeignKeys that don't already have ondelete='CASCADE'
# It captures the table name (e.g., "users.id") and the closing parenthesis or trailing args
FK_PATTERN = re.compile(r'db\.ForeignKey\((["\'].+?["\'])(?!\s*,\s*ondelete)')


def fix_models():
    for root, _, files in os.walk(MODELS_DIR):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path) as f:
                    content = f.read()

                # Replace "users.id") with "users.id", ondelete='CASCADE')
                new_content = FK_PATTERN.sub(r"db.ForeignKey(\1, ondelete='CASCADE'", content)

                if new_content != content:
                    with open(path, "w") as f:
                        f.write(new_content)
                    print(f"✅ Updated: {file}")


if __name__ == "__main__":
    fix_models()
