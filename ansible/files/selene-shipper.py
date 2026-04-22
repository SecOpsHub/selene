#!/usr/bin/env python3
"""
Selene Alert Shipper v3
Ships Wazuh alerts from alerts.json to local wazuh-indexer.

Replicates all transformations from the official Wazuh filebeat pipeline.json:
  https://github.com/wazuh/wazuh/blob/master/extensions/filebeat/7.x/wazuh-module/alerts/ingest/pipeline.json

Field mappings applied:
  @timestamp          <- timestamp (ISO8601)
  data.aws.accountId  <- data.aws.aws_account_id
  data.aws.region     <- data.aws.awsRegion
  GeoLocation         <- geoip on data.srcip, data.aws.sourceIPAddress,
                         data.aws.client_ip, data.win.eventdata.ipAddress,
                         data.aws.service.action.networkConnectionAction
                           .remoteIpDetails.ipAddressV4,
                         data.aws.httpRequest.clientIp,
                         data.gcp.jsonPayload.sourceIP,
                         data.office365.ClientIP

GeoIP database: /usr/share/wazuh-indexer/modules/ingest-geoip/GeoLite2-City.mmdb
"""
import json
import time
import os
import urllib.request
import ssl
import base64
import ipaddress
from datetime import datetime, timezone

ALERTS_FILE = '/var/ossec/logs/alerts/alerts.json'
INDEXER_URL = 'https://127.0.0.1:9200'
USERNAME = 'admin'
PASSWORD = '__INDEXER_PASSWORD__'
OFFSET_FILE = '/var/lib/selene-shipper/offset'
BATCH_SIZE = 100
SLEEP_SECONDS = 5
GEOIP_DB = '/usr/share/wazuh-indexer/modules/ingest-geoip/GeoLite2-City.mmdb'

# ── GeoIP setup ────────────────────────────────────────────────
geoip_reader = None

def init_geoip():
    global geoip_reader
    try:
        import geoip2.database
        geoip_reader = geoip2.database.Reader(GEOIP_DB)
        print("[INFO] GeoIP database loaded", flush=True)
    except ImportError:
        print("[WARN] geoip2 library not available — GeoLocation will be skipped", flush=True)
    except Exception as e:
        print(f"[WARN] Could not load GeoIP database: {e}", flush=True)


def lookup_geo(ip_str):
    """Return GeoLocation dict or None."""
    if not geoip_reader or not ip_str:
        return None
    # Skip private/reserved IPs
    try:
        addr = ipaddress.ip_address(ip_str)
        if addr.is_private or addr.is_loopback or addr.is_reserved:
            return None
    except ValueError:
        return None
    try:
        r = geoip_reader.city(ip_str)
        geo = {}
        if r.city.name:
            geo['city_name'] = r.city.name
        if r.country.name:
            geo['country_name'] = r.country.name
        if r.subdivisions and r.subdivisions.most_specific.name:
            geo['region_name'] = r.subdivisions.most_specific.name
        if r.location.latitude is not None:
            geo['location'] = {
                'lat': r.location.latitude,
                'lon': r.location.longitude
            }
        return geo if geo else None
    except Exception:
        return None


# ── Field candidates for GeoIP (in priority order, matching pipeline.json) ──
GEO_IP_FIELDS = [
    ['data', 'srcip'],
    ['data', 'win', 'eventdata', 'ipAddress'],
    ['data', 'aws', 'sourceIPAddress'],
    ['data', 'aws', 'client_ip'],
    ['data', 'aws', 'service', 'action', 'networkConnectionAction',
     'remoteIpDetails', 'ipAddressV4'],
    ['data', 'aws', 'httpRequest', 'clientIp'],
    ['data', 'gcp', 'jsonPayload', 'sourceIP'],
    ['data', 'office365', 'ClientIP'],
]


def get_nested(doc, path):
    """Safely get a nested field by path list."""
    obj = doc
    for key in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


# ── Main normalization function ────────────────────────────────
def normalize(doc):
    """
    Apply all transformations from the official Wazuh filebeat pipeline.json.
    Modifies doc in place. Returns doc.
    """

    # 1. @timestamp <- timestamp (ISO8601)
    ts = doc.get('timestamp')
    if ts and '@timestamp' not in doc:
        doc['@timestamp'] = ts

    # 2. AWS field aliases
    aws = doc.get('data', {}).get('aws', {})
    if aws:
        # data.aws.accountId <- data.aws.aws_account_id
        if 'accountId' not in aws and aws.get('aws_account_id'):
            aws['accountId'] = aws['aws_account_id']

        # data.aws.region <- data.aws.awsRegion
        if 'region' not in aws and aws.get('awsRegion'):
            aws['region'] = aws['awsRegion']

    # 3. GeoLocation — try each IP field in order, use first match
    if 'GeoLocation' not in doc:
        for field_path in GEO_IP_FIELDS:
            ip = get_nested(doc, field_path)
            if ip and isinstance(ip, str):
                geo = lookup_geo(ip)
                if geo:
                    doc['GeoLocation'] = geo
                    break

    return doc


# ── Indexer communication ──────────────────────────────────────
def get_index_name():
    return f"wazuh-alerts-4.x-{datetime.now(timezone.utc).strftime('%Y.%m.%d')}"


def post_bulk(docs, ctx):
    if not docs:
        return
    index = get_index_name()
    bulk = ''
    for doc in docs:
        bulk += json.dumps({"index": {"_index": index}}) + '\n'
        bulk += json.dumps(doc) + '\n'
    data = bulk.encode('utf-8')
    creds = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
    req = urllib.request.Request(
        f"{INDEXER_URL}/_bulk",
        data=data,
        headers={
            'Content-Type': 'application/x-ndjson',
            'Authorization': f'Basic {creds}'
        }
    )
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=30)
        result = json.loads(resp.read())
        if result.get('errors'):
            # Log first error only to avoid flooding
            for item in result.get('items', []):
                err = item.get('index', {}).get('error')
                if err:
                    print(f"[WARN] Index error: {err.get('reason', 'unknown')}", flush=True)
                    break
        else:
            print(f"[INFO] Shipped {len(docs)} docs to {index}", flush=True)
    except Exception as e:
        print(f"[ERROR] Failed to ship batch: {e}", flush=True)


# ── Offset management ──────────────────────────────────────────
def load_offset():
    os.makedirs('/var/lib/selene-shipper', exist_ok=True)
    try:
        with open(OFFSET_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return 0


def save_offset(offset):
    with open(OFFSET_FILE, 'w') as f:
        f.write(str(offset))


# ── Main loop ──────────────────────────────────────────────────
def main():
    init_geoip()

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    print("[INFO] Selene shipper v3 started", flush=True)
    offset = load_offset()
    print(f"[INFO] Starting from offset {offset}", flush=True)

    while True:
        try:
            # Detect log rotation: if file is smaller than our offset,
            # the file was rotated — reset to beginning
            try:
                file_size = os.path.getsize(ALERTS_FILE)
                if offset > file_size:
                    print(f"[INFO] Log rotation detected (offset {offset} > file size {file_size}). Resetting to 0.", flush=True)
                    offset = 0
                    save_offset(0)
            except FileNotFoundError:
                pass

            with open(ALERTS_FILE, 'rb') as f:
                f.seek(offset)
                docs = []
                while True:
                    line = f.readline()
                    if not line:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        doc = json.loads(line)
                        doc = normalize(doc)
                        docs.append(doc)
                        if len(docs) >= BATCH_SIZE:
                            post_bulk(docs, ctx)
                            docs = []
                    except json.JSONDecodeError:
                        pass
                if docs:
                    post_bulk(docs, ctx)
                new_offset = f.tell()
                if new_offset != offset:
                    offset = new_offset
                    save_offset(offset)
        except FileNotFoundError:
            print(f"[WARN] {ALERTS_FILE} not found, waiting...", flush=True)
        except Exception as e:
            print(f"[ERROR] Main loop error: {e}", flush=True)
        time.sleep(SLEEP_SECONDS)


if __name__ == '__main__':
    main()
