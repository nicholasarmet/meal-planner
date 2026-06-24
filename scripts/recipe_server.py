from __future__ import annotations
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from scripts.config import load_config, get_vault_path
from scripts.ingest_recipe import ingest_from_url
from scripts.vault import save_recipe

load_dotenv()


def create_app(config_path: str | None = None) -> Flask:
    config = load_config(config_path)
    vault_path = get_vault_path(config)
    api_key = os.environ.get("RECIPE_SERVER_API_KEY", "")

    app = Flask(__name__)

    @app.route("/add-recipe", methods=["POST"])
    def add_recipe():
        if not api_key or request.headers.get("X-API-Key") != api_key:
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        url = (data.get("url") or "").strip()
        if not url:
            return jsonify({"error": "Missing url field"}), 400
        if not url.startswith("http"):
            return jsonify({"error": "Invalid url — must start with http"}), 400
        try:
            recipe = ingest_from_url(url)
            path = save_recipe(recipe, vault_path)
            return jsonify({"status": "ok", "title": recipe.title, "path": str(path)}), 200
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5050)
