# app/tiles/boot_probe_db_auth.py

import os

import mysql.connector
from cockpit_trace import trace_log, ttl_emitter


def probe_db_auth():
    try:
        conn = mysql.connector.connect(
            host="srpihhllc.mysql.pythonanywhere-services.com",
            user="srpihhllc",
            password=os.getenv("DB_PASSWORD"),
            connection_timeout=5,
        )
        ttl_emitter("boot:db_auth", status="green", ts=True)
        trace_log("boot:db_auth", "✅ DB auth succeeded", level="info")
        conn.close()
    except Exception as e:
        ttl_emitter("boot:db_auth", status="red", ts=True)
        trace_log("boot:db_auth", f"❌ DB auth failed: {str(e)}", level="error")
