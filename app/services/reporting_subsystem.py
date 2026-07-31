# =============================================================================
# FILE: app/services/reporting_subsystem.py
# DESCRIPTION: Cockpit-grade operator background telemetry & email digest engine.
# =============================================================================

import datetime
import logging
from flask import current_app
from flask_mail import Message
from app.extensions import db, mail

logger = logging.getLogger(__name__)

def compile_system_metrics():
    """
    Aggregates operational state from the DB, Redis instances, 
    and systemic wiring matrices for the digest.
    """
    from app.models.user import User
    
    metrics = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_users": 0,
        "redis_status": "OFFLINE",
        "db_status": "HEALTHY",
        "active_operator_sessions": 0
    }
    
    try:
        # 1. Extract database metrics
        metrics["total_users"] = User.query.count()
    except Exception as e:
        metrics["db_status"] = f"DEGRADED ({str(e)})"
        logger.error(f"[REPORT ENGINE] Database metrics extraction failed: {e}")

    try:
        # 2. Extract telemetry patterns directly from your live Redis cluster extension
        # Accessing the redis client instance attached to your extensions map
        redis_client = current_app.extensions.get("redis") or current_app.extensions.get("redis_client")
        if redis_client:
            redis_client.ping()
            metrics["redis_status"] = "ONLINE"
            
            # Scan for active operator lifecycles from your token keyspace pattern
            operator_keys = redis_client.keys("operator:code:v1:*")
            metrics["active_operator_sessions"] = len(operator_keys)
    except Exception as e:
        metrics["redis_status"] = f"DISCONNECTED ({str(e)})"
        logger.error(f"[REPORT ENGINE] Redis telemetry collection failed: {e}")
        
    return metrics


def generate_html_digest_template(metrics):
    """
    Generates a professional, responsive HTML status interface 
    designed for high visibility in an inbox.
    """
    status_color = "#10b981" if "ONLINE" in metrics["redis_status"] and "HEALTHY" in metrics["db_status"] else "#f59e0b"
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f4f6f8; color: #1e293b; margin: 0; padding: 20px; }}
            .container {{ max-width: 650px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
            .header {{ background-color: #0f172a; padding: 25px; color: #ffffff; border-bottom: 4px solid {status_color}; }}
            .header h1 {{ margin: 0; font-size: 20px; letter-spacing: 0.5px; font-weight: 600; }}
            .content {{ padding: 30px; }}
            .metric-grid {{ display: table; width: 100%; margin-top: 15px; margin-bottom: 25px; }}
            .metric-row {{ display: table-row; }}
            .metric-label, .metric-value {{ display: table-cell; padding: 10px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }}
            .metric-label {{ font-weight: 500; color: #64748b; width: 40%; }}
            .metric-value {{ font-weight: 600; color: #0f172a; }}
            .badge {{ inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; text-transform: uppercase; }}
            .badge-success {{ background-color: #d1fae5; color: #065f46; }}
            .badge-warn {{ background-color: #fef3c7; color: #92400e; }}
            .footer {{ background-color: #f8fafc; padding: 15px; text-align: center; font-size: 11px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 PlaidBridge API Operational Digest</h1>
            </div>
            <div class="content">
                <p style="margin-top: 0; font-size: 15px; color: #334155;">Hello Operator, the system telemetry daemon has assembled your automated performance summary:</p>
                
                <div class="metric-grid">
                    <div class="metric-row">
                        <div class="metric-label">Report Timestamp</div>
                        <div class="metric-value">{metrics["timestamp"]}</div>
                    </div>
                    <div class="metric-row">
                        <div class="metric-label">Database Status</div>
                        <div class="metric-value">{metrics["db_status"]}</div>
                    </div>
                    <div class="metric-row">
                        <div class="metric-label">Redis Cluster</div>
                        <div class="metric-value">{metrics["redis_status"]}</div>
                    </div>
                    <div class="metric-row">
                        <div class="metric-label">Total Users Count</div>
                        <div class="metric-value">{metrics["total_users"]}</div>
                    </div>
                    <div class="metric-row">
                        <div class="metric-label">Active Operator Pins</div>
                        <div class="metric-value">{metrics["active_operator_sessions"]}</div>
                    </div>
                </div>
                
                <p style="font-size: 13px; color: #64748b; margin-bottom: 0; background: #f8fafc; padding: 12px; border-radius: 6px; border-left: 3px solid #64748b;">
                    <strong>Notice:</strong> This is an automated dashboard update from your developer sandbox context. Live logs are stream-cached inside your monitoring engine dashboard endpoints.
                </p>
            </div>
            <div class="footer">
                PlaidBridgeOpenBankingApi Framework • Secure Operator Layer v0.0.1
            </div>
        </div>
    </body>
    </html>
    """


def execute_scheduled_report_dispatch():
    """
    Core entrypoint runner executed by the background cron driver.
    Resolves the primary admin target and fires the email payload.
    """
    # Defensive application context checking
    from app.models.user import User
    
    logger.info("[REPORT ENGINE] Starting background telemetry compilation sequence...")
    
    with current_app.app_context():
        # 1. Resolve the primary authoritative administrator record dynamically
        admin_operator = User.query.filter_by(role="admin").first()
        
        if not admin_operator:
            logger.warning("[REPORT ENGINE] Aborting dispatch: No seeded administrator profile discovered.")
            return

        # 2. Extract the telemetry layer stats
        metrics = compile_system_metrics()
        
        # 3. Construct the mail message
        msg = Message(
            subject="⚙️ PlaidBridge API: Daily Cockpit Telemetry Digest",
            recipients=[admin_operator.email], # Sends directly to your configured srpollardsihhllc@gmail.com record
            html=generate_html_digest_template(metrics)
        )
        
        try:
            mail.send(msg)
            logger.info(f"✅ [REPORT ENGINE] Telemetry digest dispatched successfully to {admin_operator.email}")
        except Exception as e:
            logger.error(f"❌ [REPORT ENGINE] Critical dispatch failure over mail extension layer: {e}")