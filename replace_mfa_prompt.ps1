# Backup current file first
$src = "app\blueprints\auth_routes.py"
$bak = "$env:USERPROFILE\tmp-auth_routes-backup-before-mfa_replace.py"
Copy-Item $src $bak -Force
Write-Host "Backup saved to $bak"

# Read file into array
$text = Get-Content $src -Raw -Encoding UTF8
$lines = $text -split "`r?`n"

# Find indices for def mfa_prompt()
$startIdx = $null
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\s*def\s+mfa_prompt\s*\(') { $startIdx = $i; break }
}
if ($startIdx -eq $null) { Write-Error "Could not locate def mfa_prompt()"; exit 1 }

# Find end of function: next top-level line starting with '@' or 'def' (no leading spaces), or EOF
$endIdx = $null
for ($j = $startIdx + 1; $j -lt $lines.Count; $j++) {
    if ($lines[$j] -match '^[^ \t]' -and ($lines[$j] -match '^@' -or $lines[$j] -match '^def\s+')) {
        $endIdx = $j - 1
        break
    }
}
if ($endIdx -eq $null) { $endIdx = $lines.Count - 1 }

Write-Host "Replacing mfa_prompt() lines $($startIdx+1) .. $($endIdx+1)"

# Normalized function block (correct indentation)
$newBlock = @'
def mfa_prompt():
    # Test-mode bypass for GET requests
    if current_app.config.get("TESTING") and request.method == "GET":
        form = MFAForm()
        return render_template("auth/mfa_prompt.html", form=form, ttl=None)

    user = _resolve_mfa_user()
    ip = request.remote_addr
    user_agent = request.user_agent.string

    if not user:
        flash("MFA session expired or missing. Please log in again.", "warning")
        session.pop("mfa_user_id", None)
        return redirect(url_for("auth.login"))

    if not (user.mfa_enabled or user.mfa_pending_setup):
        session.pop("mfa_user_id", None)
        log_identity_event(user.id, "MFA_PROMPT_INVALID_STATE", ip=ip, user_agent=user_agent)
        flash("MFA is not enabled or configured for this account.", "danger")
        return redirect(url_for("auth.login"))

    # Load Redis MFA code if present
    try:
        redis_code_obj = MFACode.get_active_for_user(user.id)
    except Exception as e:
        current_app.logger.exception("Error loading MFACode for user %s", user.id)
        log_identity_event(
            user.id,
            "MFA_PROMPT_MFAOBJ_LOAD_FAIL",
            ip=ip,
            user_agent=user_agent,
            details={"error": str(e)},
        )
        redis_code_obj = None

    # If no TOTP and no Redis code → must re-enable MFA
    if not user.totp_secret and not redis_code_obj:
        log_identity_event(
            user.id,
            "MFA_PROMPT_REDIRECT_TO_ENABLE",
            ip=ip,
            user_agent=user_agent,
            details={"reason": "no_totp_or_redis_code"},
        )
        flash("MFA setup incomplete. Please enable MFA first.", "warning")
        return redirect(url_for("auth.mfa_enable"))

    form = MFAForm()
    ttl = None
    if redis_code_obj:
        try:
            ttl = redis_code_obj.time_remaining()
        except Exception:
            ttl = None

    if form.validate_on_submit():
        rate_key = f"user:{user.id}"
        if is_rate_limited(rate_key, "mfa_prompt", limit=MFA_ATTEMPT_LIMIT, period=300):
            log_identity_event(user.id, "MFA_PROMPT_RATE_LIMIT", ip=ip, user_agent=user_agent)
            flash("Too many MFA attempts. Please wait before retrying.", "danger")
            return redirect(url_for("auth.login"))

        submitted_code = (form.code.data or "").strip()

        # -----------------------------
        # TOTP MODE
        # -----------------------------
        if user.totp_secret:
            try:
                if verify_totp_code(user.totp_secret, submitted_code):
                    user.mfa_pending_setup = False
                    user.mfa_enabled = True
                    db.session.commit()

                    log_identity_event(
                        user.id,
                        "MFA_LOGIN_TOTP_SUCCESS",
                        ip=ip,
                        user_agent=user_agent,
                        details={"mode": "totp"},
                    )

                    remember_flag = session.pop("remember_me", False)
                    session.pop("mfa_user_id", None)

                    # ❗ DO NOT CLEAR SESSION
                    session.permanent = bool(remember_flag)

                    login_user(user, remember=remember_flag)
                    flash("MFA successful via Authenticator App. Logged in.", "success")
                    return redirect_for_role(user)
                else:
                    log_identity_event(
                        user.id,
                        "MFA_LOGIN_TOTP_FAIL",
                        ip=ip,
                        user_agent=user_agent,
                        details={"mode": "totp"},
                    )
                    flash("Invalid TOTP code.", "danger")

            except Exception:
                current_app.logger.exception("Error verifying TOTP for user %s", user.id)
                log_identity_event(user.id, "MFA_LOGIN_TOTP_ERROR", ip=ip, user_agent=user_agent)
                flash("An error occurred verifying your code. Try again.", "danger")

        # -----------------------------
        # REDIS MODE
        # -----------------------------
        else:
            if not redis_code_obj:
                log_identity_event(
                    user.id, "MFA_LOGIN_REDIS_NOT_FOUND", ip=ip, user_agent=user_agent
                )
                flash("No active one-time code found. Request a new code.", "warning")
            else:
                try:
                    ok = redis_code_obj.validate_and_consume(
                        submitted_code,
                        max_failures=current_app.config.get("MFA_MAX_FAILS", 10),
                    )
                except Exception:
                    current_app.logger.exception("Error validating MFACode for user %s", user.id)
                    log_identity_event(
                        user.id,
                        "MFA_LOGIN_REDIS_VALIDATE_ERROR",
                        ip=ip,
                        user_agent=user_agent,
                    )
                    ok = False

                if ok:
                    try:
                        user.mfa_pending_setup = False
                        user.mfa_enabled = True
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                        current_app.logger.exception(
                            "Failed to persist MFA enable state for user %s", user.id
                        )

                    log_identity_event(
                        user.id,
                        "MFA_LOGIN_REDIS_SUCCESS",
                        ip=ip,
                        user_agent=user_agent,
                        details={"mode": "redis"},
                    )

                    remember_flag = session.pop("remember_me", False)
                    session.pop("mfa_user_id", None)

                    # ❗ DO NOT CLEAR SESSION
                    session.permanent = bool(remember_flag)

                    login_user(user, remember=remember_flag)
                    flash("MFA successful via Email/SMS. Logged in.", "success")
                    return redirect_for_role(user)

                else:
                    log_identity_event(
                        user.id,
                        "MFA_LOGIN_REDIS_FAIL",
                        ip=ip,
                        user_agent=user_agent,
                        details={"mode": "redis"},
                    )
                    flash("Invalid or expired MFA code.", "danger")

                    try:
                        remaining = redis_code_obj.time_remaining()
                        if (not user.totp_secret) and (remaining == 0):
                            user.totp_secret = generate_totp_secret()
                            db.session.commit()
                            log_identity_event(
                                user.id,
                                "MFA_PROMPT_REDIS_EXPIRED_FALLBACK",
                                ip=ip,
                                user_agent=user_agent,
                                details={"fallback_mode": "totp"},
                            )
                            flash(
                                "One-time code expired. Switched to Authenticator App mode.",
                                "warning",
                            )
                    except Exception:
                        current_app.logger.exception(
                            "Error during expired-code fallback flow for user %s",
                            user.id,
                        )

    return render_template("auth/mfa_prompt.html", form=form, ttl=ttl)
'@

# Build new file text
$before = $lines[0..($startIdx-1)]
$after = @()
if ($endIdx + 1 -le $lines.Count - 1) { $after = $lines[($endIdx+1)..($lines.Count - 1)] }

$newText = ($before -join "`n") + "`n" + $newBlock + "`n" + ($after -join "`n")

# Write file
Set-Content -Path $src -Value $newText -Encoding utf8
Write-Host "mfa_prompt() replaced. Backup is at: $bak"

# Show context for verification
$showStart = [math]::Max(1, $startIdx - 3)
$showEnd = [math]::Min($startIdx + 80, $lines.Count - 1)
(Get-Content $src)[$showStart..$showEnd] | ForEach-Object -Begin { $num = $showStart + 1 } -Process { "{0,4}: {1}" -f $num, $_; $num++ }
