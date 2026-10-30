# =============================================================================
# FILE: app/scripts/relationship_audit.py
# DESCRIPTION: Cockpit-grade relationship audit for SQLAlchemy models.
#              Runs as a Flask CLI command with @with_appcontext.
# =============================================================================

import traceback
from typing import Any

import click
from flask import Flask
from flask.cli import with_appcontext
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Mapper, RelationshipProperty, configure_mappers


def _safe_name(obj: object) -> str:
    """Return __name__ if it is a string; otherwise return the object's string form."""
    try:
        name: Any = getattr(obj, "__name__", None)
        if isinstance(name, str):
            return name
    except Exception:
        pass

    return str(obj)


def _collect_models() -> dict[str, Mapper]:
    """Import app.models and collect its SQLAlchemy model mappers."""
    import app.models as models

    mappers: dict[str, Mapper] = {}
    for name in dir(models):
        attr = getattr(models, name, None)
        try:
            mapper = sa_inspect(attr)
        except Exception:
            continue

        if isinstance(mapper, Mapper):
            mappers[name] = mapper

    return mappers


def _has_fk_for_relationship(rel: RelationshipProperty) -> bool:
    """
    Heuristically check whether a relationship has a foreign-key link.

    For many-to-one and one-to-one relationships, the FK is usually among the
    local columns. For one-to-many relationships, it is usually on the target
    table and points back to this relationship's parent table.
    """
    try:
        local_cols = list(rel.local_columns)
        has_local_fk = any(col.foreign_keys for col in local_cols)

        target_table = rel.mapper.local_table
        our_table = rel.parent.local_table
        remote_has_fk_to_us = False

        for col in target_table.columns:
            for fk in col.foreign_keys:
                try:
                    if fk.column.table is our_table:
                        remote_has_fk_to_us = True
                        break
                except Exception:
                    # Skip foreign keys that cannot be resolved.
                    continue

            if remote_has_fk_to_us:
                break

        return bool(has_local_fk or remote_has_fk_to_us)
    except Exception:
        return False


def _check_back_populates_pair(
    rel: RelationshipProperty,
) -> tuple[bool, str]:
    """Check that back_populates exists and points to a relationship."""
    bp = rel.back_populates
    if not bp:
        return False, "missing back_populates"

    target_mapper = rel.mapper
    if not hasattr(target_mapper.class_, bp):
        return (
            False,
            f"back_populates '{bp}' not found on target "
            f"{target_mapper.class_.__name__}",
        )

    try:
        counterpart = getattr(target_mapper.class_, bp).property
        if not isinstance(counterpart, RelationshipProperty):
            return False, f"'{bp}' exists on target but is not a relationship"

        if counterpart.back_populates and counterpart.back_populates != rel.key:
            return (
                False,
                "counterpart back_populates points to "
                f"'{counterpart.back_populates}', expected '{rel.key}'",
            )
    except Exception as exc:
        return False, f"could not inspect counterpart: {exc}"

    return True, "ok"


@click.command("relationship-audit")
@with_appcontext
def relationship_audit_command() -> None:
    """
    Audit SQLAlchemy model relationships for back_populates and FK hygiene.

    Run with: flask relationship-audit
    """
    try:
        # _collect_models() imports app.models before mapper configuration.
        mappers = _collect_models()
        configure_mappers()

        if not mappers:
            click.echo(
                "❌ No mappers found. Ensure app.models imports all model files."
            )
            return

        click.echo("=== Relationship Audit ===")
        problems: list[str] = []

        for _model_name, mapper in sorted(
            mappers.items(), key=lambda item: item[0].lower()
        ):
            rels = mapper.relationships
            if not rels:
                continue

            click.echo(
                f"\nModel: {mapper.class_.__name__} "
                f"(table: {mapper.local_table.name})"
            )

            for rel in sorted(rels, key=lambda relationship: relationship.key.lower()):
                target = rel.mapper.class_.__name__
                bp = rel.back_populates or "-"
                fk_ok = _has_fk_for_relationship(rel)
                ok_bp, bp_msg = _check_back_populates_pair(rel)

                status_parts = [
                    "back_populates=OK"
                    if ok_bp
                    else f"back_populates=BAD({bp_msg})",
                    f"fk={'OK' if fk_ok else 'MISSING'}",
                ]
                status = ", ".join(status_parts)

                click.echo(
                    f" - {rel.key} -> {target}  "
                    f"[back_populates: {bp}]  [{status}]"
                )

                if not ok_bp:
                    problems.append(f"{mapper.class_.__name__}.{rel.key}: {bp_msg}")
                if not fk_ok:
                    problems.append(
                        f"{mapper.class_.__name__}.{rel.key}: "
                        "missing/undetected ForeignKey link"
                    )

        click.echo("\n=== Summary ===")
        if problems:
            click.echo(f"❌ Found {len(problems)} issue(s):")
            for problem in problems:
                click.echo(f" - {problem}")

            click.echo("\nTip:")
            click.echo(" - Ensure both sides define matching back_populates names.")
            click.echo(
                " - Ensure a ForeignKey exists on the appropriate side "
                "(e.g., the child table has db.ForeignKey('parent.id'))."
            )
            click.echo(
                " - For unconventional schemas, set primaryjoin/secondary explicitly."
            )
        else:
            click.echo("✅ No back_populates or FK issues detected.")

    except Exception:
        click.echo("❌ Audit crashed:")
        traceback.print_exc()


# -------------------------------------------------------------------------
# Registration helper
# -------------------------------------------------------------------------
def register_commands(app: Flask) -> None:
    """Register this CLI command with the Flask app."""
    app.cli.add_command(relationship_audit_command)