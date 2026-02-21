# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cockpit/tiles/mutation_submit_tile.py

from flask import Blueprint, render_template

from app.utils.redis_utils import get_redis_client

bp_mutation = Blueprint("mutation_submit_tile", __name__, url_prefix="/cockpit/mutation")


@bp_mutation.route("/")
def render_mutation_tile():
    r = get_redis_client()
    last_mutation = r.get("mutation:submit:last") if r else "None"
    return render_template("mutation_submit_tile.html", last_mutation=last_mutation)
