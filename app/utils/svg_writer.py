#!/usr/bin/env python3
# =============================================================================
# FILE: app/utils/svg_writer.py
# DESCRIPTION: Hardened vector graphic manipulation engine layer.
#              Remediates B314 / CWE-20 structural XML parser vulnerabilities
#              by integrating defusedxml defensively against XXE injections.
# =============================================================================

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import defusedxml.ElementTree as ET  # Remediates Bandit B314: Safe drop-in deflator engine

# Instantiate localized structured operational logger
logger = logging.getLogger("svg_writer")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

# Resolve absolute pathing matrix relative to deployment workspace environments
DEFAULT_SVG_ASSET = Path("static/docs/fintech-orchestration-v2.drawio.svg")


def add_model_to_svg(
    model_name: str, target_file_path: Path = DEFAULT_SVG_ASSET
) -> None:
    """
    Securely parses system layout vector manifests, targets architectural node hooks,
    and appends domain-specific database entity models into the graphic map.
    """
    if not target_file_path.exists():
        logger.error(
            "Target data resolution failure: Asset node missing at boundary path: %s",
            target_file_path,
        )
        sys.exit(1)

    try:
        # Remediates Bandit B314 / CWE-20: Disables DTD parsing, external entities, and entity loops
        tree = ET.parse(str(target_file_path))
        root = tree.getroot()
    except Exception:
        logger.exception(
            "Structural syntax breakdown encountered while evaluating target SVG stream blueprint."
        )
        sys.exit(3)

    # Locate schema container by targeting explicit draw.io structural tracking IDs
    schema_group = root.find(".//*[@id='relational-schema']")
    if schema_group is None:
        logger.error(
            "❌ Mapping target constraint failure: 'relational-schema' selector identity missing from DOM."
        )
        return

    # Construct secure, isolated XML Element tree node vectors
    new_group = ET.Element("g")

    ET.SubElement(
        new_group,
        "rect",
        {
            "x": "400",
            "y": "160",
            "width": "160",
            "height": "40",
            "fill": "#00ffe7",
            "stroke": "#121212",
            "stroke-width": "1",
        },
    )

    text_node = ET.SubElement(
        new_group,
        "text",
        {"x": "410", "y": "185", "fill": "#121212", "font-size": "14"},
    )
    text_node.text = model_name

    # Commit mutated structural nodes into localized tree allocations
    schema_group.append(new_group)

    try:
        # Defensive Safeguard: Force explicit reservation of default vector namespace maps.
        # Eliminates native ElementTree serialization artifacts from prepending unreadable tags (like ns0:)
        ET.register_namespace("", "http://www.w3.org/2000/svg")

        # Write clean structural changes back to the source document location
        tree.write(
            str(target_file_path), encoding="utf-8", xml_declaration=True
        )
        logger.info(
            "✅ Successfully bound structural model token identity [%s] into file mapping topology.",
            model_name,
        )
    except Exception:
        logger.exception(
            "Write synchronization crash tracking structural delta changes back to disk storage footprint."
        )
        sys.exit(4)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Secure structural asset modification tool adjusting blueprint architecture schemas."
    )
    parser.add_argument(
        "--add",
        type=str,
        required=True,
        help="Target alphanumeric database model entity name to append into rendering layouts.",
    )
    args = parser.parse_args()

    add_model_to_svg(args.add)


if __name__ == "__main__":
    main()
