# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli/svg_writer.py

import argparse
import xml.etree.ElementTree as ET


def add_model_to_svg(model_name):
    svg_file = "static/docs/fintech-orchestration-v2.drawio.svg"
    tree = ET.parse(svg_file)
    root = tree.getroot()

    # Locate schema block — use draw.io class or title
    schema_group = root.find(".//*[@id='relational-schema']")
    if schema_group is None:
        print("❌ Could not find schema block.")
        return

    # Create a new rect + text element (simplified)
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
    ET.SubElement(
        new_group,
        "text",
        {"x": "410", "y": "185", "fill": "#121212", "font-size": "14"},
    ).text = model_name

    schema_group.append(new_group)
    tree.write(svg_file)
    print(f"✅ Added {model_name} to SVG.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add model to system SVG.")
    parser.add_argument("--add", type=str, help="Model name to insert")
    args = parser.parse_args()
    if args.add:
        add_model_to_svg(args.add)
