# app/blueprints/todo_routes.py

import logging
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models.todo import Todo
from app.models.user_dashboard import UserDashboard

logger = logging.getLogger(__name__)

# Subscriber-only Todo blueprint
todo_bp = Blueprint("todo", __name__, url_prefix="/sub/todos")


# -------------------------------------------------------------------------
# Role guard
# -------------------------------------------------------------------------
def _require_subscriber():
    """
    Only authenticated subscribers may access /sub/todos routes.
    """
    if not current_user.is_authenticated:
        abort(401)
    if getattr(current_user, "role", None) != "subscriber":
        abort(403)
    return current_user


# -------------------------------------------------------------------------
# Dashboard settings helpers
# -------------------------------------------------------------------------
def _get_dashboard_settings(user) -> dict:
    """
    Ensure UserDashboard exists and return settings.
    """
    dashboard = getattr(user, "user_dashboard", None)
    if dashboard is None:
        dashboard = UserDashboard.create_for_user(user.id)
        db.session.add(dashboard)
        db.session.commit()
    return dashboard.settings or UserDashboard.default_settings()


def _apply_sort_and_filter(query, settings: dict):
    """
    Apply sort/filter preferences from UserDashboard.settings to a Todo query.
    """
    sort = settings.get("todo_sort", "created")  # created | priority | due
    flt = settings.get("todo_filter", "all")  # all | pending | completed | overdue | high

    # Filter
    if flt == "pending":
        query = query.filter_by(completed=False)
    elif flt == "completed":
        query = query.filter_by(completed=True)
    elif flt == "overdue":
        query = query.filter_by(completed=False).filter(Todo.due_date < datetime.utcnow().date())
    elif flt == "high":
        query = query.filter_by(priority="high")

    # Sort
    if sort == "priority":
        # high > normal > low
        query = query.order_by(
            db.case(
                (Todo.priority == "high", 1),
                (Todo.priority == "normal", 2),
                (Todo.priority == "low", 3),
                else_=4,
            ),
            Todo.created_at.desc(),
        )
    elif sort == "due":
        query = query.order_by(Todo.due_date.is_(None), Todo.due_date.asc())
    else:  # created
        query = query.order_by(Todo.created_at.desc())

    return query


# -------------------------------------------------------------------------
# List Todos
# -------------------------------------------------------------------------
@todo_bp.route("/", endpoint="list", methods=["GET"])
@login_required
def list_todos():
    user = _require_subscriber()
    settings = _get_dashboard_settings(user)

    query = Todo.query.filter_by(user_id=user.id)
    query = _apply_sort_and_filter(query, settings)
    todos = query.all()

    today = datetime.utcnow().date()

    # Derived counts
    pending_count = Todo.query.filter_by(user_id=user.id, completed=False).count()
    completed_count = Todo.query.filter_by(user_id=user.id, completed=True).count()
    overdue_count = (
        Todo.query.filter_by(user_id=user.id, completed=False).filter(Todo.due_date < today).count()
    )

    return render_template(
        "todo/todo_list.html",
        todos=todos,
        settings=settings,
        pending_count=pending_count,
        completed_count=completed_count,
        overdue_count=overdue_count,
        current_date=today,
    )


# -------------------------------------------------------------------------
# Add Todo
# -------------------------------------------------------------------------
@todo_bp.route("/add", methods=["POST"])
@login_required
def add_todo():
    user = _require_subscriber()
    settings = _get_dashboard_settings(user)

    text = request.form.get("text", "").strip()
    if not text:
        flash("Todo text cannot be empty.", "warning")
        return redirect(url_for("todo.list"))

    priority = request.form.get("priority") or settings.get("default_priority", "normal")
    category = request.form.get("category") or settings.get("default_category")
    due_date_raw = request.form.get("due_date") or None
    notes = request.form.get("notes") or None

    due_date = None
    if due_date_raw:
        try:
            due_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
        except ValueError:
            due_date = None

    todo = Todo(
        user_id=user.id,
        text=text,
        priority=priority,
        category=category,
        due_date=due_date,
        notes=notes,
        completed=False,
    )

    db.session.add(todo)
    db.session.commit()

    logger.info(f"Todo created by user={user.id}: {text!r}")

    flash("Todo added.", "success")
    return redirect(url_for("todo.list"))


# -------------------------------------------------------------------------
# Toggle Todo (completed)
# -------------------------------------------------------------------------
@todo_bp.route("/toggle/<int:todo_id>", methods=["POST"])
@login_required
def toggle(todo_id):
    user = _require_subscriber()
    todo = Todo.query.filter_by(id=todo_id, user_id=user.id).first_or_404()

    todo.completed = not todo.completed
    db.session.commit()

    logger.info(f"Todo toggled by user={user.id}: id={todo_id}, completed={todo.completed}")

    return redirect(url_for("todo.list"))


# -------------------------------------------------------------------------
# Update Todo (edit modal)
# -------------------------------------------------------------------------
@todo_bp.route("/update/<int:todo_id>", methods=["POST"])
@login_required
def update_todo(todo_id):
    user = _require_subscriber()
    todo = Todo.query.filter_by(id=todo_id, user_id=user.id).first_or_404()

    # Update core fields
    todo.text = request.form.get("text", todo.text).strip()
    todo.priority = request.form.get("priority", todo.priority)
    todo.category = request.form.get("category", todo.category)
    todo.notes = request.form.get("notes", todo.notes)

    # Due date handling
    due_raw = request.form.get("due_date")
    if due_raw:
        try:
            todo.due_date = datetime.strptime(due_raw, "%Y-%m-%d").date()
        except ValueError:
            pass  # ignore invalid dates

    db.session.commit()

    logger.info(
        f"Todo updated by user={user.id}: id={todo_id}, "
        f"text={todo.text!r}, priority={todo.priority}, category={todo.category}"
    )

    flash("Todo updated.", "success")
    return redirect(url_for("todo.list"))


# -------------------------------------------------------------------------
# Delete Todo
# -------------------------------------------------------------------------
@todo_bp.route("/delete/<int:todo_id>", methods=["POST"])
@login_required
def delete(todo_id):
    user = _require_subscriber()
    todo = Todo.query.filter_by(id=todo_id, user_id=user.id).first_or_404()

    db.session.delete(todo)
    db.session.commit()

    logger.info(f"Todo deleted by user={user.id}: id={todo_id}")

    flash("Todo deleted.", "info")
    return redirect(url_for("todo.list"))
