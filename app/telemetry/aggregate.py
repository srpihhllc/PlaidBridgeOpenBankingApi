# app/utils/telemetry/aggregate.py
def mark_cluster_alive(rc, host, ttl):
    rc.sadd("ttl:boot:instances", host)
    rc.expire("ttl:boot:instances", ttl)
