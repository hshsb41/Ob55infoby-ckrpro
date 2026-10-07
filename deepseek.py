# ============================================================
#  ██████╗ ██████╗ ██╗███╗   ███╗███████╗    ███████╗███████╗
#  ██╔══██╗██╔══██╗██║████╗ ████║██╔════╝    ██╔════╝██╔════╝
#  ██████╔╝██████╔╝██║██╔████╔██║█████╗      █████╗  █████╗
#  ██╔═══╝ ██╔══██╗██║██║╚██╔╝██║██╔══╝      ██╔══╝  ██╔══╝
#  ██║     ██║  ██║██║██║ ╚═╝ ██║███████╗    ██║     ██║
#  ╚═╝     ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝    ╚═╝     ╚═╝
#
#  PRIME FF — AUTO-REGION FINDER INFO API
#  FULLY FIXED FOR ALL PLATFORMS
#  NO EXTERNAL API KEY REQUIRED
#  JOIN @primeff55 FOR MORE LEAKS
# ============================================================

import asyncio
import time
import httpx
import json
import random
import threading
import os
import sys
import base64
from collections import defaultdict
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
from cachetools import TTLCache
from typing import Tuple, Optional
from proto import FreeFire_pb2, main_pb2, AccountPersonalShow_pb2
from google.protobuf import json_format, message
from google.protobuf.message import Message
from Crypto.Cipher import AES
import logging

# ---------- PRIME FF Logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PRIME-FF")

# ---------- Config ----------
MAIN_KEY = base64.b64decode('WWcmdGMlREV1aDYlWmNeOA==')
MAIN_IV = base64.b64decode('Nm95WkRyMjJFM3ljaGpNJQ==')
RELEASEVERSION = "OB55"
USERAGENT = "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)"

# jwt.py wala UnityPlayer UA (MajorLogin ke liye better)
LOGIN_USERAGENT = "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)"

SUPPORTED_REGIONS = [
    "IND", "SG", "ID", "BR", "VN", "US", "SAC", "NA",
    "RU", "TH", "TW", "BD", "PK", "ME", "CIS", "EUROPE"
]

# ---------- App Setup ----------
app = Flask(__name__)
CORS(app)
cache = TTLCache(maxsize=200, ttl=600)
uid_region_cache = TTLCache(maxsize=200, ttl=3600)
cached_tokens = defaultdict(dict)

# ---------- Shared HTTP client ----------
HTTP_LIMITS = httpx.Limits(max_keepalive_connections=20, max_connections=50)
HTTP_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
_http_client: Optional[httpx.Client] = None

def http_sync() -> httpx.Client:
    """Sync client (MajorLogin jwt.py wala)."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(limits=HTTP_LIMITS, timeout=HTTP_TIMEOUT)
    return _http_client

_http_async: Optional[httpx.AsyncClient] = None
def http() -> httpx.AsyncClient:
    """Async client (account info ke liye)."""
    global _http_async
    if _http_async is None:
        _http_async = httpx.AsyncClient(limits=HTTP_LIMITS, timeout=HTTP_TIMEOUT)
    return _http_async

# ---------- Helpers ----------
def pad(text: bytes) -> bytes:
    padding_length = AES.block_size - (len(text) % AES.block_size)
    return text + bytes([padding_length] * padding_length)

def aes_cbc_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(plaintext))

def decode_protobuf(encoded_data: bytes, message_type: message.Message):
    instance = message_type()
    try:
        instance.ParseFromString(encoded_data)
        return instance
    except Exception as e:
        logger.error(f"Protobuf decode error: {e}")
        return None

async def json_to_proto(json_data: str, proto_message: Message) -> bytes:
    json_format.ParseDict(json.loads(json_data), proto_message)
    return proto_message.SerializeToString()

# ---------- jwt.py wala extract_login_res (scanning trick) ----------
def _try_parse_login_res(data: bytes):
    try:
        msg = FreeFire_pb2.LoginRes()
        msg.ParseFromString(data)
        if msg.account_id and msg.account_id > 0:
            return json.loads(json_format.MessageToJson(msg))
    except Exception:
        pass
    return None

def extract_login_res(raw: bytes) -> dict:
    """PRIME FF: scan technique from jwt.py — handles prefixed/truncated responses."""
    # Attempt 1: from index 0
    parsed = _try_parse_login_res(raw)
    if parsed:
        return parsed

    # Attempt 2: scan each \x08 (protobuf field-1 varint start)
    idx = 0
    while True:
        idx = raw.find(b"\x08", idx)
        if idx == -1:
            break
        parsed = _try_parse_login_res(raw[idx:])
        if parsed:
            return parsed
        idx += 1

    # Attempt 3: JWT marker prefix (eyJhbGciOiJIUzI1NiIs...)
    jwt_marker = raw.find(b"eyJhbGciOiJIUzI1NiIs")
    if jwt_marker != -1:
        for i in range(jwt_marker - 1, max(jwt_marker - 300, -1), -1):
            if raw[i] == 0x42:
                parsed = _try_parse_login_res(raw[i:])
                if parsed:
                    return parsed
                break

    raise Exception(f"PRIME FF: Could not parse LoginRes. Raw: {raw[:200]}")

# ---------- Guest IDS (UNCHANGED) ----------
def get_account_credentials(region: str) -> str:
    r = region.upper()

    credentials = {
        "IND": "uid=4587290647&password=BUNNY_FLASH_SBQ8W",
        "BR": "uid=4774366356&password=ADD_HERE",
        "US": "uid=4774366356&password=ADD_HERE",
        "SAC": "uid=4774366356&password=ADD_HERE",
        "NA": "uid=4774366356&password=ADD_HERE",
        "VN": "uid=4737714557&password=ADD_HERE",
        "SG": "uid=4737718961&password=ADD_HERE",
        "ID": "uid=4737720872&password=ADD_HERE",
        "TH": "uid=4774298073&password=ADD_HERE",
        "TW": "uid=4774314170&password=ADD_HERE",
        "BD": "uid=4423054565&password=CKR_PRO_BOT_WF9AMKXDI",
        "PK": "uid=4774330898&password=ADD_HERE",
        "ME": "uid=4774339389&password=ADD_HERE",
        "RU": "uid=4774345536&password=ADD_HERE",
        "CIS": "uid=4774350397&password=ADD_HERE",
        "EUROPE": "uid=4774375811&password=ADD_HERE"
    }

    if r in credentials:
        return credentials[r]

    try:
        with open("ucguest.txt", "r") as f:
            lines = [line.strip() for line in f if line.strip()]
            if not lines:
                raise ValueError("ucguest.txt is empty")
            uid, password = random.choice(lines).split()
            return f"uid={uid}&password={password}"
    except Exception as e:
        logger.error(f"Guest file error: {e}")
        return "uid=4587290647&password=BUNNY_FLASH_SBQ8W"

# ---------- OAuth guest token ----------
def get_access_token(account: str):
    """PRIME FF: jwt.py wala — sync httpx, better headers."""
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    payload = (
        account
        + "&response_type=token&client_type=2"
        + "&client_secret=2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
        + "&client_id=100067"
    )
    headers = {
        "User-Agent": LOGIN_USERAGENT,
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    try:
        resp = http_sync().post(url, data=payload, headers=headers)
        data = resp.json()
        return data.get("access_token", "0"), data.get("open_id", "0")
    except Exception as e:
        logger.error(f"PRIME FF OAuth error: {e}")
        return "0", "0"

# ---------- MajorLogin (jwt.py system — internal JWT) ----------
def generate_jwt_token(uid: str, password: str):
    """
    PRIME FF: Direct MajorLogin JWT generation.
    External API hata di — ab ye khud token banata hai.
    """
    start_time = time.time()

    token_val, open_id = get_access_token(f"uid={uid}&password={password}")
    if token_val == "0" or open_id == "0":
        raise Exception("PRIME FF: Invalid UID/Password — access token not received")

    body = json.dumps({
        "open_id": open_id,
        "open_id_type": "4",
        "login_token": token_val,
        "orign_platform_type": "4",
    })
    proto_bytes = json_to_proto_sync(body, FreeFire_pb2.LoginReq())
    payload = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, proto_bytes)

    headers = {
        "User-Agent": LOGIN_USERAGENT,
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "X-Ga-Sv": "1789534056",
        "Authorization": "Bearer",
        "X-Ga": "v1 1",
        "Releaseversion": RELEASEVERSION,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
        "PlAy_VeR": "1.132.1",
        "Ob_VeR": RELEASEVERSION,
    }

    resp = http_sync().post(
        "https://loginbp.ppmainecoonghj.com/MajorLogin",
        data=payload, headers=headers
    )

    # PRIME FF: body check
    if resp.status_code != 200:
        raise Exception(f"MajorLogin HTTP {resp.status_code}: {resp.text[:80]}")
    if "text/" in resp.headers.get("content-type", ""):
        raise Exception(f"MajorLogin rejected: {resp.text[:80]}")

    msg = extract_login_res(resp.content)
    elapsed = time.time() - start_time

    return {
        "access_token": token_val,
        "open_id": open_id,
        "real_uid": str(msg.get("accountId", "")),
        "status": "success",
        "time": f"{elapsed:.2f}s",
        "token": msg.get("token", ""),
        "lock_region": msg.get("lockRegion", ""),
        "server_url": msg.get("serverUrl", ""),
    }

def json_to_proto_sync(json_data: str, proto_message: Message) -> bytes:
    """Sync version (jwt.py wala)."""
    json_format.ParseDict(json.loads(json_data), proto_message)
    return proto_message.SerializeToString()

# ---------- Token cache per region ----------
async def create_jwt(region: str):
    """PRIME FF: MajorLogin internal JWT — external API replace kar diya."""
    try:
        account = get_account_credentials(region)
        # account format: "uid=X&password=Y" — split
        parts = dict(p.split("=", 1) for p in account.split("&"))
        uid = parts.get("uid", "")
        password = parts.get("password", "")

        if not uid or not password or password == "ADD_HERE":
            logger.warning(f"PRIME FF [{region}]: guest creds missing (ADD_HERE)")
            return

        token_data = await asyncio.get_event_loop().run_in_executor(
            None, generate_jwt_token, uid, password
        )

        if not token_data.get("token"):
            logger.error(f"PRIME FF [{region}]: no token in LoginRes")
            return

        server_url = token_data.get("server_url") or "https://clientbp.ppmainecoonghj.com"
        lock_region = token_data.get("lock_region") or region

        cached_tokens[region] = {
            'token': f"Bearer {token_data['token']}",
            'region': lock_region,
            'server_url': server_url,
            'expires_at': time.time() + 25200,
        }
        logger.info(f"✅ PRIME FF [{region}] Token OK "
                    f"(real_uid={token_data['real_uid']}, {token_data['time']})")

    except Exception as e:
        logger.error(f"PRIME FF [{region}] create_jwt error: {e}")

async def get_token_info(region: str) -> Tuple[str, str, str]:
    info = cached_tokens.get(region)
    if info and time.time() < info.get('expires_at', 0):
        return info['token'], info['region'], info['server_url']

    await create_jwt(region)
    info = cached_tokens.get(region)
    if not info:
        raise RuntimeError(f"PRIME FF: No token for {region}")
    return info['token'], info['region'], info['server_url']

async def initialize_tokens():
    logger.info("🔥 PRIME FF: Initializing tokens for all regions...")
    tasks = [create_jwt(r) for r in SUPPORTED_REGIONS]
    await asyncio.gather(*tasks, return_exceptions=True)

async def refresh_tokens_periodically():
    while True:
        await asyncio.sleep(25200)
        await initialize_tokens()

# ---------- Get Account Information ----------
async def GetAccountInformation(uid, unk, region, endpoint):
    try:
        payload = await json_to_proto(
            json.dumps({'a': uid, 'b': unk}),
            main_pb2.GetPlayerPersonalShow()
        )

        data_enc = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, payload)
        token, lock, server = await get_token_info(region)

        headers = {
            'User-Agent': USERAGENT,
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Content-Type': "application/octet-stream",
            'Expect': "100-continue",
            'Authorization': token,
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': RELEASEVERSION,
        }

        r = await http().post(server + endpoint, data=data_enc, headers=headers)

        if r.status_code != 200:
            logger.error(f"PRIME FF: account info failed {r.status_code} region={region}")
            return None
        if "text/" in r.headers.get("content-type", ""):
            return None

        decoded = decode_protobuf(r.content,
                                  AccountPersonalShow_pb2.AccountPersonalShowInfo)
        if not decoded:
            return None

        return json.loads(json_format.MessageToJson(decoded))
    except Exception as e:
        logger.error(f"PRIME FF GetAccountInformation: {e}")
        return None

# ---------- Cache decorator ----------
def cached_endpoint(ttl=300):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            key = (request.path, tuple(request.args.items()))
            if key in cache:
                return cache[key]
            res = fn(*a, **k)
            cache[key] = res
            return res
        return wrapper
    return decorator

# ============================================================
#  PRIME FF Routes
# ============================================================

@app.route('/info', methods=['GET'])
@cached_endpoint()
def get_account_info():
    """PRIME FF main endpoint: /info?uid=123456789"""
    uid = request.args.get('uid')

    if not uid:
        return jsonify({"error": "PRIME FF: Please provide UID. Usage: /info?uid=123456789"}), 400

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Cached region fast path
    if uid in uid_region_cache:
        try:
            data = loop.run_until_complete(
                GetAccountInformation(uid, "7", uid_region_cache[uid],
                                      "/GetPlayerPersonalShow")
            )
            if data:
                return jsonify(data)
        except Exception as e:
            logger.error(f"PRIME FF: cached region failed: {e}")

    # Try every region
    for region in SUPPORTED_REGIONS:
        try:
            data = loop.run_until_complete(
                GetAccountInformation(uid, "7", region, "/GetPlayerPersonalShow")
            )
            if data:
                uid_region_cache[uid] = region
                return jsonify(data)
        except Exception as e:
            logger.debug(f"PRIME FF: region {region} failed: {e}")
            continue

    return jsonify({"error": "PRIME FF: UID not found or account doesn't exist"}), 404

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "active",
        "brand": "PRIME FF",
        "regions": len(SUPPORTED_REGIONS),
        "cached_tokens": len(cached_tokens),
        "cache_size": len(cache),
    }), 200

@app.route('/refresh-tokens', methods=['GET', 'POST'])
def refresh_tokens_endpoint():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(initialize_tokens())
        return jsonify({'message': 'PRIME FF: tokens refreshed successfully'}), 200
    except Exception as e:
        return jsonify({'error': f'PRIME FF: {e}'}), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "name": "PRIME FF — FreeFire Auto-Region Finder API",
        "version": "3.0",
        "brand": "PRIME FF",
        "endpoints": {
            "/info": "Get account info — Usage: /info?uid=123456789",
            "/health": "Health check",
            "/refresh-tokens": "Force refresh tokens",
        },
        "status": "running",
    }), 200

# ---------- Error Handlers ----------
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "PRIME FF: endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "PRIME FF: internal server error"}), 500

# ---------- Startup ----------
started = False

def start_background_loop():
    global started
    if started:
        return
    started = True

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(initialize_tokens())
        loop.create_task(refresh_tokens_periodically())
        loop.run_forever()
    except Exception as e:
        logger.error(f"PRIME FF background loop error: {e}")

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'

    thread = threading.Thread(target=start_background_loop, daemon=True)
    thread.start()

    logger.info(f"🔥 PRIME FF starting on {host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)

if __name__ == '__main__':
    if os.environ.get('VERCEL'):
        app.config['ENV'] = 'production'
        app.config['DEBUG'] = False
        threading.Thread(target=start_background_loop, daemon=True).start()
    else:
        run_flask()