# app/services/letter_renderer.py

from pathlib import Path

from jinja2 import Template


def render_letter(template_name, context):
    path = Path(f"app/templates/letters/{template_name}")
    if not path.exists():
        raise FileNotFoundError(f"Template {template_name} not found")

    with open(path) as f:
        template = Template(f.read())
    return template.render(context)
