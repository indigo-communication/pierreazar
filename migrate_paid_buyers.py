#!/usr/bin/env python3
"""Idempotently migrate verified paid buyers to Premium Member accounts.

Dry-run by default:
    python3 migrate_paid_buyers.py

Apply with backups and send setup emails:
    python3 migrate_paid_buyers.py --apply --send-emails
"""

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import server


MIGRATION_VERSION = "premium-buyers-v1"
ACCEPTED_GATEWAY_STATUSES = {"AUTHORIZED", "CAPTURED", "PARTIAL_AUTHORIZED"}


def load_json(path):
    path = Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def verified_paid_orders():
    sales = load_json(server.SALES_FILE)
    paid_sale_ids = {
        str(sale.get("order_id", "")).strip()
        for sale in sales
        if sale.get("status") == "paid" and sale.get("order_id")
    }
    verified = []
    review = []
    for order in load_json(server.ORDERS_FILE):
        order_id = str(order.get("order_id", "")).strip()
        email = server._normalize_email(order.get("email"))
        status = str(order.get("gateway_status", "")).upper()
        has_gateway_proof = bool(
            status in ACCEPTED_GATEWAY_STATUSES
            or order.get("cybersource_id")
            or order.get("success_indicator")
        )
        valid = (
            order.get("status") == "paid"
            and order_id in paid_sale_ids
            and email
            and server._EMAIL_RE.match(email)
            and has_gateway_proof
        )
        if valid:
            verified.append(order)
        elif order.get("status") == "paid":
            review.append(order_id or "(missing order ID)")
    verified.sort(key=lambda item: str(item.get("paid_at") or item.get("date") or ""))
    return verified, review


def backup_data():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = Path(server.DATA_DIR) / "backups" / f"premium-migration-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    for source in (
        server.MEMBERS_FILE,
        server.ORDERS_FILE,
        server.SALES_FILE,
        server.PASSWORD_SETUP_TOKENS_FILE,
    ):
        source = Path(source)
        if source.exists():
            shutil.copy2(source, backup_dir / source.name)
    return backup_dir


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write member/setup-token data")
    parser.add_argument("--send-emails", action="store_true", help="email new pending-password members")
    args = parser.parse_args()
    if args.send_emails and not args.apply:
        parser.error("--send-emails requires --apply")

    orders, review = verified_paid_orders()
    members = load_json(server.MEMBERS_FILE)
    existing = {
        server._normalize_email(member.get("email")): member
        for member in members
    }
    by_email = {}
    for order in orders:
        by_email.setdefault(server._normalize_email(order.get("email")), []).append(order)

    create_count = 0
    upgrade_count = 0
    already_migrated_count = 0
    for email in by_email:
        member = existing.get(email)
        if member is None:
            create_count += 1
        elif MIGRATION_VERSION in member.get("migrations", []):
            already_migrated_count += 1
        elif not member.get("premium"):
            upgrade_count += 1

    summary = {
        "mode": "apply" if args.apply else "dry-run",
        "verified_orders": len(orders),
        "unique_paid_buyers": len(by_email),
        "accounts_to_create": create_count,
        "existing_accounts_to_upgrade": upgrade_count,
        "already_migrated": already_migrated_count,
        "paid_orders_needing_review": review,
    }
    print(json.dumps(summary, indent=2))
    if not args.apply:
        return

    backup_dir = backup_data()
    print(f"backup_dir={backup_dir}")
    email_sent = []
    email_failed = []
    base_url = server.get_payment_config().get("return_base_url", "https://pierreazar.com")

    for email, buyer_orders in by_email.items():
        before = existing.get(email) or {}
        was_migrated = MIGRATION_VERSION in before.get("migrations", [])
        result = None
        for order in buyer_orders:
            result = server._upsert_premium_buyer(order, migration_version=MIGRATION_VERSION)
        if (
            result
            and result["needs_password_setup"]
            and not was_migrated
            and args.send_emails
        ):
            latest_order = buyer_orders[-1]
            try:
                server._issue_password_setup_email(latest_order, base_url)
                email_sent.append(email)
            except Exception as exc:
                server._log_email_error(
                    f"premium_migration:{latest_order.get('order_id', '')}",
                    exc,
                )
                email_failed.append({"email": email, "error": str(exc)})

    report = {
        **summary,
        "mode": "applied",
        "backup_dir": str(backup_dir),
        "setup_emails_sent": email_sent,
        "setup_email_failures": email_failed,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    report_path = backup_dir / "migration-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
