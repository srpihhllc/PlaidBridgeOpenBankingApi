# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/registry/routes.py

from flask import Blueprint, render_template

from app.models.registry import Registry

registry_bp = Blueprint("registry", __name__, url_prefix="/registry")


@registry_bp.route("/", methods=["GET"])
def show_registry():
    regs = Registry.query.order_by(Registry.name).all()
    return render_template("registry.html", registries=regs)
