# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils/trace_probe.py

import argparse
import json
from collections import Counter

from flask import current_app

from app.utils.redis_utils import get_redis_client  # ✅ centralised, SSL‑safe client


def scan_keys(pattern):
    r = get_redis_client()
    if not r:
        current_app.logger.error(
            f"[trace_probe] Redis unavailable — cannot scan keys for pattern={pattern}"
        )
        return []
    cursor = "0"
    keys = []
    while True:
        cursor, batch = r.scan(cursor=cursor, match=pattern, count=100)
        keys.extend(batch)
        if cursor == "0":
            break
    return keys


def rank_ttl(ttl):
    if ttl is None or ttl < 0:
        return "⛔ Expired or no TTL"
    if ttl > 3600:
        return "🟢 Fresh"
    elif ttl > 600:
        return "🟡 Aging"
    else:
        return "🔴 Stale"


def render_trace(key, raw, ttl):
    print("—" * 60)
    print(f"🔑 Key:         {key}")
    print(f"⏳ TTL:         {ttl} seconds")
    print(f"🧪 Freshness:   {rank_ttl(ttl)}")
    try:
        trace = json.loads(raw)
        print(f"📍 IP:          {trace.get('ip')}")
        print(f"📦 Path:        {trace.get('path')}")
        print(f"🔁 Method:      {trace.get('method')}")
        print(f"🔗 Referer:     {trace.get('referer')}")
        print(f"🧭 User-Agent:  {trace.get('ua')}")
        print(f"🕒 Timestamp:   {trace.get('timestamp')}")
        print(f"📘 Event Type:  {trace.get('event_type', 'UNKNOWN')}")
    except Exception as e:
        print(f"⚠️ Failed to parse JSON: {e}")
        print(f"Raw Value: {raw}")
    print("—" * 60)


def dump_traces(pattern):
    r = get_redis_client()
    if not r:
        current_app.logger.error(
            f"[trace_probe] Redis unavailable — cannot dump traces for pattern={pattern}"
        )
        return

    keys = scan_keys(pattern)
    print(f"\n🔍 Found {len(keys)} keys matching '{pattern}'\n")

    types = Counter()
    for key in keys:
        raw = r.get(key)
        ttl = r.ttl(key)
        if raw:
            try:
                trace = json.loads(raw.decode("utf-8"))
                types[trace.get("event_type", "UNKNOWN")] += 1
                render_trace(key, raw.decode("utf-8"), ttl)
            except Exception as e:
                print(f"⚠️ Error parsing trace: {e}")

    print(f"\n📘 Event Type Summary: {dict(types)}\n")


def show_counts(ip_list):
    r = get_redis_client()
    if not r:
        current_app.logger.error("[trace_probe] Redis unavailable — cannot show counts")
        return

    print("\n📊 Repeat Offender Counts\n")
    for ip in ip_list:
        key = f"trace:bad_method_count:{ip}"
        count = r.get(key)
        print(f"{key}: {count.decode('utf-8') if count else '0'}")


def rank_offenders(keys):
    r = get_redis_client()
    if not r:
        current_app.logger.error("[trace_probe] Redis unavailable — cannot rank offenders")
        return

    ip_list = []
    for key in keys:
        raw = r.get(key)
        if raw:
            try:
                trace = json.loads(raw.decode("utf-8"))
                ip = trace.get("ip")
                if ip:
                    ip_list.append(ip)
            except Exception:
                continue
    counter = Counter(ip_list)
    print("\n📊 IP Frequency Ranking:\n")
    for ip, count in counter.most_common():
        print(f"{ip}: {count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern", type=str, default="trace:route_mismatch:*")
    parser.add_argument("--count", nargs="*", help="IP(s) to check repeat count", default=[])
    parser.add_argument("--rank", action="store_true", help="Rank offending IPs by frequency")
    parser.add_argument("--boot", action="store_true", help="Inspect boot rollback skip traces")
    args = parser.parse_args()

    if args.boot:
        dump_traces("boot/identity_rollback_skipped")
    else:
        dump_traces(args.pattern)

    if args.count:
        show_counts(args.count)

    if args.rank:
        rank_offenders(scan_keys(args.pattern))
