import requests
import re
import smtplib
import os
import json
import time
import uuid
import random
import csv
import io
import datetime
import threading

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict, Counter
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from openpyxl import Workbook
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_file

app = Flask(__name__, static_url_path='/static')
app.secret_key = "telsocanad"

SESSIONS = {}
BLOCKED_IPS = set()

USER_AGENT = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1"
]

PROXIES_LIST = []


class RotatingRequester:
    def __init__(self):
        self.user_agent_index = 0
        self.proxy_index = 0
        self.lock = threading.Lock()
        self.failed_proxies = set()

    def get_next_user_agent(self):
        with self.lock:
            user_agent = USER_AGENT[self.user_agent_index]
            self.user_agent_index = (self.user_agent_index + 1) % len(USER_AGENT)
            return user_agent

    def get_next_proxy(self):
        if not PROXIES_LIST:
            return None

        with self.lock:
            attempts = 0
            while attempts < len(PROXIES_LIST):
                proxy = PROXIES_LIST[self.proxy_index]
                proxy_key = f"{proxy['http']}"
                self.proxy_index = (self.proxy_index + 1) % len(PROXIES_LIST)

                if proxy_key not in self.failed_proxies:
                    return proxy

                attempts += 1

            if attempts >= len(PROXIES_LIST):
                self.failed_proxies.clear()
                return PROXIES_LIST[0]

            return None

    def mark_proxy_failed(self, proxy):
        if proxy:
            proxy_key = f"{proxy['http']}"
            with self.lock:
                self.failed_proxies.add(proxy_key)

    def _build_headers(self, url):
        user_agent = self.get_next_user_agent()
        parsed = urlparse(url)
        host = parsed.netloc

        headers = {
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }

        if "tikwm.com" in host:
            headers["Referer"] = "https://www.tikwm.com/"
            headers["Origin"] = "https://www.tikwm.com"
        elif "tiktok.com" in host:
            headers["Referer"] = "https://www.tiktok.com/"
        else:
            headers["Referer"] = f"{parsed.scheme}://{host}/"

        return headers

    def make_request(self, url, timeout=10):
        proxy = self.get_next_proxy()
        headers = self._build_headers(url)

        if proxy:
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    proxies=proxy,
                    timeout=timeout,
                    verify=False
                )
                if response.status_code == 200:
                    return response
                else:
                    self.mark_proxy_failed(proxy)
            except Exception as e:
                self.mark_proxy_failed(proxy)
                print(f"Proxy hatası: {str(e)}")

        try:
            response = requests.get(url, headers=headers, timeout=timeout, verify=False)
            return response
        except Exception as e:
            print(f"Direkt bağlantı hatası: {str(e)}")
            raise e


requester = RotatingRequester()


@app.before_request
def block_ips():
    if request.remote_addr in BLOCKED_IPS:
        return jsonify({"error": "IP engellenmiş"}), 403


@app.after_request
def add_security_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Server"] = "Hidden"
    return response


USERS_FILE = "users.json"
USER_STATES_FILE = "user_states.json"


def today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def default_user_meta(role="user"):
    return {
        "role": role,
        "created_at": now_str(),
        "last_login": None,
        "last_login_device": None,
        "is_frozen": False,
        "package_type": "premium" if role == "admin" else "trial",
        "account_type": "premium" if role == "admin" else "trial",   # trial / premium
        "daily_scrape_limit": 999999 if role == "admin" else 50,
        "total_scrape_limit": 999999999 if role == "admin" else 500,
        "daily_scrape_used": 0,
        "total_scrape_used": 0,
        "daily_export_count": 0,
        "total_export_count": 0,
        "daily_mail_found": 0,
        "total_mail_found": 0,
        "last_usage_reset_date": today_str(),
        "total_active_seconds": 0,
        "last_ip": None
    }


DEFAULT_USERS = {
    "talha": {
        "password": "kaka9900",
        **default_user_meta("admin"),
        "created_at": "2024-01-01 00:00:00"
    },
    "telo": {
        "password": "telo9900",
        **default_user_meta("user"),
        "created_at": "2024-01-01 00:00:00"
    }
}


def ensure_user_record(username, user_data):
    role = user_data.get("role", "user")
    defaults = default_user_meta(role)
    for key, value in defaults.items():
        if key not in user_data:
            user_data[key] = value

    if "password" not in user_data:
        user_data["password"] = ""

    if not user_data.get("last_usage_reset_date"):
        user_data["last_usage_reset_date"] = today_str()

    if role == "admin":
        if user_data.get("daily_scrape_limit", 0) < 999999:
            user_data["daily_scrape_limit"] = 999999
        if user_data.get("total_scrape_limit", 0) < 999999999:
            user_data["total_scrape_limit"] = 999999999
        if not user_data.get("package_type"):
            user_data["package_type"] = "premium"
        if not user_data.get("account_type"):
            user_data["account_type"] = "premium"

    return user_data


def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
                if not isinstance(users, dict):
                    return DEFAULT_USERS.copy()
                for uname in list(users.keys()):
                    users[uname] = ensure_user_record(uname, users[uname])
                return users
        except:
            return DEFAULT_USERS.copy()
    return DEFAULT_USERS.copy()


def save_users(users):
    for uname in list(users.keys()):
        users[uname] = ensure_user_record(uname, users[uname])
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def normalize_queue_item(item):
    if isinstance(item, dict):
        return {
            "user_id": str(item.get("user_id", "")).strip(),
            "sec_uid": str(item.get("sec_uid", "")).strip() or None
        }
    elif isinstance(item, str):
        return {"user_id": item.strip(), "sec_uid": None}
    return {"user_id": "", "sec_uid": None}


def build_queue_item(user_id=None, sec_uid=None):
    return {
        "user_id": str(user_id).strip() if user_id is not None else "",
        "sec_uid": str(sec_uid).strip() if sec_uid else None
    }


def get_queue_key(queue_item):
    item = normalize_queue_item(queue_item)
    if item.get("sec_uid"):
        return f"sec:{item['sec_uid']}"
    if item.get("user_id"):
        return f"uid:{item['user_id']}"
    return None


def parse_region_filter(value):
    if not value:
        return []

    if isinstance(value, list):
        items = value
    else:
        items = str(value).replace(";", ",").split(",")

    regions = []
    seen = set()

    for item in items:
        code = str(item).strip().upper()
        if code and code not in seen:
            seen.add(code)
            regions.append(code)

    return regions


def make_result_key(result):
    sec_uid = str(result.get("sec_uid") or "").strip()
    user_id = str(result.get("user_id") or "").strip()
    username = str(result.get("username") or "").strip().lower()
    email = str(result.get("email") or "").strip().lower()

    if sec_uid:
        return f"sec:{sec_uid}"
    if user_id:
        return f"uid:{user_id}"
    return f"user:{username}|mail:{email}"


def safe_int(value, default=0):
    try:
        return int(value)
    except:
        return default


def is_rate_limit_message(text):
    if not text:
        return False
    lowered = str(text).lower()
    return (
        "free api limit" in lowered
        or "1 request/second" in lowered
        or "too many request" in lowered
        or "too many requests" in lowered
        or "rate limit" in lowered
    )


def snapshot_queue(queue_obj, limit=10):
    try:
        with queue_obj.mutex:
            items = list(queue_obj.queue)[:limit]
        return [normalize_queue_item(item) for item in items]
    except:
        return []


def format_duration(seconds):
    seconds = safe_int(seconds, 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, sec = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}"


def reset_user_usage_if_needed(username):
    global USERS
    if username not in USERS:
        return

    USERS[username] = ensure_user_record(username, USERS[username])
    current_day = today_str()

    if USERS[username].get("last_usage_reset_date") != current_day:
        USERS[username]["daily_scrape_used"] = 0
        USERS[username]["daily_export_count"] = 0
        USERS[username]["daily_mail_found"] = 0
        USERS[username]["last_usage_reset_date"] = current_day
        save_users(USERS)


def increment_scrape_usage(username, amount=1):
    global USERS
    if username not in USERS:
        return
    reset_user_usage_if_needed(username)
    USERS[username]["daily_scrape_used"] = safe_int(USERS[username].get("daily_scrape_used", 0)) + safe_int(amount, 1)
    USERS[username]["total_scrape_used"] = safe_int(USERS[username].get("total_scrape_used", 0)) + safe_int(amount, 1)
    save_users(USERS)


def increment_export_usage(username, amount=1):
    global USERS
    if username not in USERS:
        return
    reset_user_usage_if_needed(username)
    USERS[username]["daily_export_count"] = safe_int(USERS[username].get("daily_export_count", 0)) + safe_int(amount, 1)
    USERS[username]["total_export_count"] = safe_int(USERS[username].get("total_export_count", 0)) + safe_int(amount, 1)
    save_users(USERS)


def increment_mail_found_usage(username, amount=1):
    global USERS
    if username not in USERS:
        return
    reset_user_usage_if_needed(username)
    USERS[username]["daily_mail_found"] = safe_int(USERS[username].get("daily_mail_found", 0)) + safe_int(amount, 1)
    USERS[username]["total_mail_found"] = safe_int(USERS[username].get("total_mail_found", 0)) + safe_int(amount, 1)
    save_users(USERS)


def add_active_seconds(username, seconds):
    global USERS
    if username not in USERS:
        return
    USERS[username]["total_active_seconds"] = safe_int(USERS[username].get("total_active_seconds", 0)) + safe_int(seconds, 0)
    save_users(USERS)


def can_user_scrape(username, planned_amount=1):
    if username not in USERS:
        return False, "Kullanıcı bulunamadı"

    reset_user_usage_if_needed(username)
    user = USERS[username]

    if user.get("is_frozen"):
        return False, "Hesap dondurulmuş. Yönetici ile iletişime geçin."

    if user.get("role") == "admin":
        return True, ""

    daily_limit = safe_int(user.get("daily_scrape_limit", 0), 0)
    total_limit = safe_int(user.get("total_scrape_limit", 0), 0)
    daily_used = safe_int(user.get("daily_scrape_used", 0), 0)
    total_used = safe_int(user.get("total_scrape_used", 0), 0)

    if daily_limit > 0 and (daily_used + planned_amount) > daily_limit:
        return False, f"Günlük scrape hakkınız doldu. ({daily_used}/{daily_limit})"

    if total_limit > 0 and (total_used + planned_amount) > total_limit:
        return False, f"Toplam kullanım limitiniz doldu. ({total_used}/{total_limit})"

    return True, ""


def load_user_states():
    if os.path.exists(USER_STATES_FILE):
        try:
            with open(USER_STATES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

                for username in data:
                    if 'queue_items' in data[username]:
                        queue = Queue()
                        for item in data[username]['queue_items']:
                            queue.put(normalize_queue_item(item))
                        data[username]['queue'] = queue
                        del data[username]['queue_items']
                    else:
                        data[username]['queue'] = Queue()

                    if 'queued_users_list' in data[username]:
                        data[username]['queued_users'] = set(data[username]['queued_users_list'])
                        del data[username]['queued_users_list']
                    else:
                        data[username]['queued_users'] = set()

                    if 'processed_list' in data[username]:
                        data[username]['processed'] = set(data[username]['processed_list'])
                        del data[username]['processed_list']
                    else:
                        data[username]['processed'] = set()

                    if 'unique_emails_list' in data[username]:
                        data[username]['unique_emails'] = set(data[username]['unique_emails_list'])
                        del data[username]['unique_emails_list']
                    else:
                        data[username]['unique_emails'] = set()

                    if 'result_keys_list' in data[username]:
                        data[username]['result_keys'] = set(data[username]['result_keys_list'])
                        del data[username]['result_keys_list']
                    else:
                        data[username]['result_keys'] = set()

                    if 'results' not in data[username]:
                        data[username]['results'] = []

                    if 'start_time' in data[username] and data[username]['start_time']:
                        if isinstance(data[username]['start_time'], str):
                            try:
                                data[username]['start_time'] = datetime.datetime.fromisoformat(data[username]['start_time'])
                            except:
                                data[username]['start_time'] = None

                    if 'scraping_thread' not in data[username]:
                        data[username]['scraping_thread'] = None

                    if 'executor' not in data[username]:
                        data[username]['executor'] = None

                    if 'batch_counter' not in data[username]:
                        data[username]['batch_counter'] = 0

                    if 'filters' not in data[username]:
                        data[username]['filters'] = {}

                    if 'region_filter' not in data[username]['filters']:
                        data[username]['filters']['region_filter'] = []

                    if 'current_processing_user_id' not in data[username]:
                        data[username]['current_processing_user_id'] = None

                    if 'skipped_count' not in data[username]:
                        data[username]['skipped_count'] = 0

                    if 'rate_limit_waits' not in data[username]:
                        data[username]['rate_limit_waits'] = 0

                    if 'scrape_session_start' not in data[username]:
                        data[username]['scrape_session_start'] = None

                return data
        except Exception as e:
            print(f"Kullanıcı durumları yüklenirken hata: {e}")
            return {}
    return {}


def save_user_states():
    try:
        data = {}
        for username, state in user_states.items():
            serializable_state = state.copy()

            queue_items = []
            temp_queue = Queue()
            while not state['queue'].empty():
                try:
                    item = state['queue'].get_nowait()
                    item = normalize_queue_item(item)
                    queue_items.append(item)
                    temp_queue.put(item)
                except:
                    break

            while not temp_queue.empty():
                try:
                    state['queue'].put(temp_queue.get_nowait())
                except:
                    break

            serializable_state['queue_items'] = queue_items
            del serializable_state['queue']

            serializable_state['queued_users_list'] = list(state['queued_users'])
            serializable_state['processed_list'] = list(state['processed'])
            serializable_state['unique_emails_list'] = list(state['unique_emails'])
            serializable_state['result_keys_list'] = list(state['result_keys'])

            del serializable_state['queued_users']
            del serializable_state['processed']
            del serializable_state['unique_emails']
            del serializable_state['result_keys']

            if 'scraping_thread' in serializable_state:
                del serializable_state['scraping_thread']

            if 'executor' in serializable_state:
                del serializable_state['executor']

            if 'start_time' in serializable_state and serializable_state['start_time']:
                if isinstance(serializable_state['start_time'], datetime.datetime):
                    serializable_state['start_time'] = serializable_state['start_time'].isoformat()

            if 'scrape_session_start' in serializable_state and serializable_state['scrape_session_start']:
                if isinstance(serializable_state['scrape_session_start'], datetime.datetime):
                    serializable_state['scrape_session_start'] = serializable_state['scrape_session_start'].isoformat()

            if 'logs' in serializable_state:
                for log in serializable_state['logs']:
                    if 'timestamp' in log and isinstance(log.get('timestamp'), datetime.datetime):
                        log['timestamp'] = log['timestamp'].strftime("%H:%M:%S")

            if 'mail_logs' in serializable_state:
                for log in serializable_state['mail_logs']:
                    if 'timestamp' in log and isinstance(log.get('timestamp'), datetime.datetime):
                        log['timestamp'] = log['timestamp'].strftime("%H:%M:%S")

            if 'recent_users' in serializable_state:
                for user in serializable_state['recent_users']:
                    if 'timestamp' in user and isinstance(user.get('timestamp'), datetime.datetime):
                        user['timestamp'] = user['timestamp'].strftime("%H:%M:%S")

            if 'results' in serializable_state:
                for result in serializable_state['results']:
                    if 'timestamp' in result and isinstance(result.get('timestamp'), datetime.datetime):
                        result['timestamp'] = result['timestamp'].strftime("%H:%M:%S")

            data[username] = serializable_state

        with open(USER_STATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Kullanıcı durumları kaydedilirken hata: {e}")


USERS = load_users()

TELEGRAM_TOKEN = "6400322599:AAHqnXZK2-3JAgSmnC2TTpPZGtHKBipecm8"
TELEGRAM_CHAT_ID = "-1002301538284"

saved_states = load_user_states()
user_states = defaultdict(lambda: {
    'queue': Queue(),
    'queued_users': set(),
    'processed': set(),
    'unique_emails': set(),
    'result_keys': set(),
    'results': [],
    'logs': [],
    'is_scraping': False,
    'mail_logs': [],
    'start_time': None,
    'recent_users': [],
    'batch_counter': 0,
    'current_processing_user_id': None,
    'skipped_count': 0,
    'rate_limit_waits': 0,
    'scrape_session_start': None,
    'filters': {
        'min_followers': 0,
        'max_followers': 9999999,
        'verified_filter': 'any',
        'email_filter': 'all',
        'ttseller_filter': 'any',
        'region_filter': []
    },
    'smtp_settings': {},
    'scraping_thread': None,
    'executor': None
})

for username, state in saved_states.items():
    user_states[username].update(state)
    if 'filters' not in user_states[username]:
        user_states[username]['filters'] = {}
    if 'region_filter' not in user_states[username]['filters']:
        user_states[username]['filters']['region_filter'] = []
    if 'result_keys' not in user_states[username]:
        user_states[username]['result_keys'] = set()
    if 'results' not in user_states[username]:
        user_states[username]['results'] = []
    if 'current_processing_user_id' not in user_states[username]:
        user_states[username]['current_processing_user_id'] = None
    if 'skipped_count' not in user_states[username]:
        user_states[username]['skipped_count'] = 0
    if 'rate_limit_waits' not in user_states[username]:
        user_states[username]['rate_limit_waits'] = 0
    if 'scrape_session_start' not in user_states[username]:
        user_states[username]['scrape_session_start'] = None

lock = threading.Lock()
SAVE_BATCH_SIZE = 25
PROCESSED_USERS_FILE = "talhabvaba.txt"

if not os.path.exists(PROCESSED_USERS_FILE):
    with open(PROCESSED_USERS_FILE, 'w', encoding='utf-8') as f:
        pass

global_processed_users = set()
file_write_lock = threading.Lock()


def load_processed_users():
    global global_processed_users
    try:
        with open(PROCESSED_USERS_FILE, "r", encoding='utf-8') as f:
            lines = f.read().strip().splitlines()
            global_processed_users = set(line.strip() for line in lines if line.strip())
        print(f"Processed users yüklendi: {len(global_processed_users)} kullanıcı")
    except Exception as e:
        print(f"Processed users yüklenirken hata: {e}")
        global_processed_users = set()
    return global_processed_users


load_processed_users()


def periodic_save():
    while True:
        time.sleep(35)
        save_user_states()


save_thread = threading.Thread(target=periodic_save, daemon=True)
save_thread.start()


def save_processed_users_batch(secuids):
    global global_processed_users

    if not secuids:
        return

    with file_write_lock:
        try:
            existing_users = set()
            if os.path.exists(PROCESSED_USERS_FILE):
                with open(PROCESSED_USERS_FILE, "r", encoding='utf-8') as f:
                    existing_users = set(line.strip() for line in f.read().strip().splitlines() if line.strip())

            new_users = []
            for secuid in secuids:
                if secuid and secuid not in existing_users and secuid not in global_processed_users:
                    new_users.append(secuid)
                    global_processed_users.add(secuid)

            if new_users:
                with open(PROCESSED_USERS_FILE, "a", encoding='utf-8') as f:
                    for secuid in new_users:
                        f.write(secuid + "\n")
                print(f"Dosyaya {len(new_users)} yeni secUid eklendi")
        except Exception as e:
            print(f"Processed users kaydedilirken hata: {e}")


def format_followers(count):
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.1f}K"
    else:
        return str(count)


def is_valid_email(email, email_filter):
    if email_filter == "all":
        return True
    elif email_filter == "valid":
        allowed_domains = ["gmail.com"]
        domain = email.split('@')[-1].lower()
        return domain in allowed_domains
    return True


def is_probable_shop(uid, bio):
    keywords = ["shop", "store", "beauty", "cosmetic", "products", "dm to order", "order", "shopping", "products sold"]
    all_text = f"{uid} {bio}".lower()
    return any(kw in all_text for kw in keywords)


def notify_telegram_login(username, ip, agent, success=True):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
        data = response.json()
        country = data.get("country", "Bilinmiyor")
        city = data.get("city", "Bilinmiyor")
    except:
        country = city = "Bilinmiyor"

    status = "? <b>Başarılı Giriş</b>" if success else "? <b>Hatalı Giriş Denemesi</b>"
    msg = f"""{status}
?? <b>Kullanıcı:</b> <code>{username}</code>
?? <b>IP:</b> <code>{ip}</code>
??? <b>Konum:</b> {country} / {city}
?? <b>Saat:</b> {now}
?? <b>Cihaz:</b> <code>{agent}</code>"""

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
        )
    except:
        pass


def get_current_username():
    return session.get("username")


def is_user_authenticated():
    username = session.get("username")
    token = session.get("token")
    return (
        session.get("logged_in") and
        username and
        token and
        username in SESSIONS and
        SESSIONS[username] == token
    )


def extract_user_id_and_secuid_from_profile_html(html):
    user_id = None
    sec_uid = None

    patterns_user_id = [
        r'"id":"(\d+)"',
        r'"authorId":"(\d+)"',
        r'"userId":"(\d+)"',
        r'"uid":"(\d+)"'
    ]
    patterns_secuid = [
        r'"secUid":"(.*?)"',
        r'"sec_uid":"(.*?)"'
    ]

    for pattern in patterns_user_id:
        match = re.search(pattern, html)
        if match:
            user_id = match.group(1)
            break

    for pattern in patterns_secuid:
        match = re.search(pattern, html)
        if match:
            sec_uid = match.group(1)
            break

    return user_id, sec_uid


def get_following_api_url(user_id, count=200, time_cursor=0):
    return f"https://www.tikwm.com/api/user/following?user_id={user_id}&count={count}&time={time_cursor}"


def extract_following_users(data):
    if not isinstance(data, dict):
        return []

    possible_sources = [
        data.get("userList"),
        data.get("users"),
        data.get("followings"),
        data.get("following_list"),
        data.get("data")
    ]

    data_obj = data.get("data")
    if isinstance(data_obj, dict):
        possible_sources.extend([
            data_obj.get("userList"),
            data_obj.get("users"),
            data_obj.get("followings"),
            data_obj.get("following_list"),
            data_obj.get("list"),
        ])

    for source in possible_sources:
        if isinstance(source, list):
            return source

    return []


def parse_user_entry(user):
    if not isinstance(user, dict):
        return None

    user_data = user.get("user", user)
    stats_data = user.get("stats", user.get("authorStats", {}))

    uid = (
        user_data.get("unique_id")
        or user_data.get("uniqueId")
        or user_data.get("username")
        or ""
    )
    verified = bool(user_data.get("verified", False))
    followers = (
        user_data.get("follower_count")
        or stats_data.get("follower_count")
        or stats_data.get("followerCount")
        or user_data.get("followerCount")
        or 0
    )
    signature = (
        user_data.get("signature")
        or user_data.get("bio")
        or user_data.get("desc")
        or ""
    )
    secuid = user_data.get("sec_uid") or user_data.get("secUid") or ""
    user_id = user_data.get("id") or user_data.get("uid") or user_data.get("user_id") or ""
    region = (user_data.get("region") or "").strip().upper()
    following_count = (
        user_data.get("following_count")
        or stats_data.get("following_count")
        or stats_data.get("followingCount")
        or 0
    )
    ttseller = bool(
        user_data.get("ttSeller", False)
        or user_data.get("tt_seller", False)
        or user_data.get("isSeller", False)
    )

    followers = safe_int(followers, 0)
    following_count = safe_int(following_count, 0)

    return {
        "uid": str(uid).strip(),
        "verified": verified,
        "followers": followers,
        "following_count": following_count,
        "signature": str(signature).strip(),
        "secuid": str(secuid).strip(),
        "user_id": str(user_id).strip(),
        "ttseller": ttseller,
        "region": region
    }


def add_result_to_state(username, state, result_entry):
    result_key = make_result_key(result_entry)
    if result_key in state["result_keys"]:
        return False

    state["result_keys"].add(result_key)
    state["results"].append(result_entry)

    if len(state["results"]) > 50000:
        state["results"] = state["results"][-50000:]

    if result_entry.get("email") and not result_entry.get("is_duplicate"):
        increment_mail_found_usage(username, 1)

    return True


def process_single_user(queue_item, username, filters):
    global global_processed_users
    state = user_states[username]
    item = normalize_queue_item(queue_item)

    current_user_id = item.get("user_id")
    current_sec_uid = item.get("sec_uid")

    if not current_user_id:
        return "general_error", [{
            "type": "error",
            "message": f" Geçersiz user_id: {queue_item}",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
        }]

    if current_sec_uid and (current_sec_uid in state["processed"] or current_sec_uid in global_processed_users):
        return "already_processed", [], current_sec_uid

    try:
        url = get_following_api_url(current_user_id, count=200, time_cursor=0)
        response = requester.make_request(url, timeout=13)

        try:
            data = response.json()
            users = extract_following_users(data)
        except Exception as e:
            error_log = {
                "type": "error",
                "message": f" JSON hatası: user_id={current_user_id} | Hata: {str(e)} | HTTP: {response.status_code}",
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
            }
            return "json_error", [error_log], current_sec_uid

        api_msg = ""
        if isinstance(data, dict):
            api_msg = data.get("msg") or data.get("message") or ""

        if is_rate_limit_message(api_msg):
            warning_log = {
                "type": "warning",
                "message": f" Rate limit: user_id={current_user_id} | {api_msg}",
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
            }
            return "rate_limited", [warning_log], current_sec_uid

        if not users:
            warning_log = {
                "type": "warning",
                "message": f"Gizli hesap / veri yok: user_id={current_user_id}" + (f" | {api_msg}" if api_msg else ""),
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
            }
            return "no_data", [warning_log], current_sec_uid

        logs = []
        new_users = []
        region_filter = filters.get("region_filter", [])

        for raw_user in users:
            parsed = parse_user_entry(raw_user)
            if not parsed:
                continue

            uid = parsed["uid"]
            verified = parsed["verified"]
            followers = parsed["followers"]
            signature = parsed["signature"]
            secuid = parsed["secuid"]
            next_user_id = parsed["user_id"]
            ttseller = parsed["ttseller"]
            region = parsed["region"]
            followers_str = format_followers(followers)

            if region_filter and region not in region_filter:
                continue
            if filters["ttseller_filter"] == "ttseller" and not ttseller:
                continue
            if filters["verified_filter"] == "verified" and not verified:
                continue
            if filters["verified_filter"] == "unverified" and verified:
                continue
            if not (filters["min_followers"] <= followers <= filters["max_followers"]):
                continue

            match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", signature)
            email = match.group(0) if match else None
            shop_emoji = " ???" if ttseller else ""
            verified_emoji = " ?" if verified else ""
            region_text = f" | {region}" if region else ""

            is_duplicate_email = False
            if email and email in state["unique_emails"]:
                is_duplicate_email = True

            result_entry = {
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                "username": uid,
                "email": email,
                "followers": followers_str,
                "followers_raw": followers,
                "verified": verified,
                "ttseller": ttseller,
                "is_shop": ttseller or is_probable_shop(uid, signature),
                "is_duplicate": is_duplicate_email,
                "user_id": next_user_id,
                "sec_uid": secuid,
                "region": region,
                "signature": signature
            }

            log_entry = {
                "type": "success" if email and is_valid_email(email, filters["email_filter"]) and not is_duplicate_email else "info",
                "message": "",
                "timestamp": result_entry["timestamp"],
                **result_entry
            }

            if email and is_valid_email(email, filters["email_filter"]):
                if is_duplicate_email:
                    log_entry["type"] = "warning"
                    log_entry["message"] = f" {uid}: Tekrarlayan e-posta ({email}) | {followers_str} takipçi{region_text}{shop_emoji}{verified_emoji}"
                else:
                    state["unique_emails"].add(email)
                    log_entry["message"] = f" {uid}:{email} | {followers_str} takipçi{region_text}{shop_emoji}{verified_emoji}"
            elif email:
                log_entry["type"] = "warning"
                log_entry["message"] = f" {uid}: Filtreye uymayan e-posta | {followers_str} takipçi{region_text}{shop_emoji}{verified_emoji}"
            else:
                log_entry["message"] = f" {uid}: E-posta yok | {followers_str} takipçi{region_text}{shop_emoji}{verified_emoji}"

            logs.append(log_entry)
            add_result_to_state(username, state, result_entry)

            if next_user_id:
                queue_candidate = build_queue_item(user_id=next_user_id, sec_uid=secuid)
                queue_key = get_queue_key(queue_candidate)

                if (
                    queue_key
                    and secuid
                    and secuid not in state["processed"]
                    and secuid not in global_processed_users
                    and queue_key not in state["queued_users"]
                ):
                    if ttseller or email or is_probable_shop(uid, signature):
                        new_users.append(queue_candidate)

        return "success", logs, new_users, current_sec_uid

    except Exception as e:
        error_log = {
            "type": "error",
            "message": f" Genel hata: user_id={current_user_id} | {str(e)}",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
        }
        return "general_error", [error_log], current_sec_uid


def build_region_analysis(results):
    region_users = Counter()
    region_emails = Counter()

    seen_users_per_region = defaultdict(set)
    seen_email_per_region = defaultdict(set)

    for item in results:
        region = item.get("region") or "UNKNOWN"
        user_key = item.get("sec_uid") or item.get("user_id") or item.get("username") or str(uuid.uuid4())
        email = item.get("email")

        if user_key not in seen_users_per_region[region]:
            seen_users_per_region[region].add(user_key)
            region_users[region] += 1

        if email:
            email_key = email.lower().strip()
            if email_key not in seen_email_per_region[region]:
                seen_email_per_region[region].add(email_key)
                region_emails[region] += 1

    rows = []
    for region in sorted(set(list(region_users.keys()) + list(region_emails.keys()))):
        user_count = region_users.get(region, 0)
        email_count = region_emails.get(region, 0)
        ratio = round((email_count / user_count) * 100, 2) if user_count > 0 else 0
        rows.append({
            "region": region,
            "users_found": user_count,
            "emails_found": email_count,
            "email_ratio": ratio
        })

    top_regions = sorted(rows, key=lambda x: (x["email_ratio"], x["emails_found"], x["users_found"]), reverse=True)[:10]
    return {
        "rows": rows,
        "top_regions": top_regions
    }


def build_chart_data(results):
    region_counter = Counter()
    verified_counter = {"verified": 0, "unverified": 0}
    shop_counter = {"shop": 0, "normal": 0}
    email_counter = {"with_email": 0, "without_email": 0}
    timeline_counter = Counter()

    seen_users = set()

    for item in results:
        user_key = item.get("sec_uid") or item.get("user_id") or item.get("username")
        if user_key and user_key in seen_users:
            continue
        if user_key:
            seen_users.add(user_key)

        region = item.get("region") or "UNKNOWN"
        region_counter[region] += 1

        if item.get("verified"):
            verified_counter["verified"] += 1
        else:
            verified_counter["unverified"] += 1

        if item.get("is_shop"):
            shop_counter["shop"] += 1
        else:
            shop_counter["normal"] += 1

        if item.get("email"):
            email_counter["with_email"] += 1
            timestamp = item.get("timestamp")
            if timestamp:
                minute_key = timestamp[:5]
                timeline_counter[minute_key] += 1
        else:
            email_counter["without_email"] += 1

    timeline_rows = [{"time": k, "count": timeline_counter[k]} for k in sorted(timeline_counter.keys())]

    return {
        "region_distribution": [{"label": k, "value": v} for k, v in region_counter.most_common()],
        "verified_distribution": [
            {"label": "Verified", "value": verified_counter["verified"]},
            {"label": "Unverified", "value": verified_counter["unverified"]}
        ],
        "shop_distribution": [
            {"label": "Shop", "value": shop_counter["shop"]},
            {"label": "Normal", "value": shop_counter["normal"]}
        ],
        "email_distribution": [
            {"label": "Mail Var", "value": email_counter["with_email"]},
            {"label": "Mail Yok", "value": email_counter["without_email"]}
        ],
        "email_timeline": timeline_rows
    }


def filter_results_list(results, args):
    region_filter = parse_region_filter(args.get("region", ""))
    email_only = args.get("email_only", "false").lower() == "true"
    verified_only = args.get("verified_only", "false").lower() == "true"
    shop_type = args.get("shop_type", "all").lower()
    search = str(args.get("search", "")).strip().lower()

    filtered = []
    for item in results:
        if email_only and not item.get("email"):
            continue
        if verified_only and not item.get("verified"):
            continue
        if region_filter and (item.get("region") or "") not in region_filter:
            continue
        if shop_type == "shop" and not item.get("is_shop"):
            continue
        if shop_type == "normal" and item.get("is_shop"):
            continue

        if search:
            haystack = " ".join([
                str(item.get("username", "")),
                str(item.get("email", "")),
                str(item.get("region", "")),
                str(item.get("user_id", "")),
                str(item.get("sec_uid", "")),
                str(item.get("signature", ""))
            ]).lower()
            if search not in haystack:
                continue

        filtered.append(item)

    return filtered


def start_scrape_session(username):
    state = user_states[username]
    state["scrape_session_start"] = datetime.datetime.now()


def finish_scrape_session(username):
    state = user_states[username]
    started = state.get("scrape_session_start")
    if started:
        if isinstance(started, str):
            try:
                started = datetime.datetime.fromisoformat(started)
            except:
                started = None
        if started:
            elapsed = int((datetime.datetime.now() - started).total_seconds())
            if elapsed > 0:
                add_active_seconds(username, elapsed)
    state["scrape_session_start"] = None


@app.route("/")
def index():
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if is_user_authenticated():
        return render_template("dashboard.html", username=session.get("username"), role=session.get("role"))
    return redirect(url_for("index"))


@app.route("/login", methods=["POST"])
def login():
    global USERS
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    ip = request.remote_addr
    agent = request.headers.get("User-Agent")

    if username in USERS:
        USERS[username] = ensure_user_record(username, USERS[username])

    if username in USERS and USERS[username]["password"] == password:
        if USERS[username].get("is_frozen"):
            notify_telegram_login(username, ip, agent, success=False)
            return jsonify({"success": False, "message": "Hesap dondurulmuş. Yönetici ile iletişime geçin."}), 403

        token = str(uuid.uuid4())
        session["logged_in"] = True
        session["token"] = token
        session["username"] = username
        session["role"] = USERS[username]["role"]

        SESSIONS[username] = token

        USERS[username]["last_login"] = now_str()
        USERS[username]["last_login_device"] = agent
        USERS[username]["last_ip"] = ip
        reset_user_usage_if_needed(username)
        save_users(USERS)

        notify_telegram_login(username, ip, agent, success=True)
        return jsonify({
            "success": True,
            "token": token,
            "role": USERS[username]["role"],
            "package_type": USERS[username].get("package_type"),
            "account_type": USERS[username].get("account_type")
        })
    else:
        notify_telegram_login(username, ip, agent, success=False)
        return jsonify({"success": False, "message": "Geçersiz kullanıcı adı veya şifre"}), 401


@app.route("/logout", methods=["POST"])
def logout():
    username = session.get("username")

    if username and username in SESSIONS:
        del SESSIONS[username]

    if username in user_states and user_states[username]["is_scraping"]:
        finish_scrape_session(username)

    session.clear()
    return jsonify({"success": True})


@app.route("/start_scraper", methods=["POST"])
def start_scraper():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    username = get_current_username()
    state = user_states[username]

    with lock:
        if state["is_scraping"]:
            return jsonify({"error": "Zaten bir işlem devam ediyor."}), 400

    allowed, reason = can_user_scrape(username, 1)
    if not allowed:
        return jsonify({"error": reason}), 403

    data = request.get_json()
    user_id = str(data.get("userId") or data.get("user_id") or "").strip()

    if not user_id:
        return jsonify({"error": "userId gerekli"}), 400

    min_followers = safe_int(data.get("minFollowers", 0), 0)
    max_followers = safe_int(data.get("maxFollowers", 9999999), 9999999)

    state["filters"].update({
        "min_followers": min_followers,
        "max_followers": max_followers,
        "verified_filter": data.get("verifiedFilter", "any"),
        "email_filter": data.get("emailFilter", "all"),
        "ttseller_filter": data.get("ttsellerFilter", "any"),
        "region_filter": parse_region_filter(data.get("regionFilter", ""))
    })

    increment_scrape_usage(username, 1)
    start_scrape_session(username)

    thread = threading.Thread(
        target=scrape,
        args=(username, user_id),
        daemon=True
    )
    state["scraping_thread"] = thread
    thread.start()

    return jsonify({
        "message": "Veri toplama işlemi başlatıldı.",
        "filters": state["filters"]
    })


def scrape(username, start_user_id):
    global global_processed_users
    state = user_states[username]
    filters = state["filters"]

    load_processed_users()

    initial_item = build_queue_item(user_id=start_user_id, sec_uid=None)
    initial_key = get_queue_key(initial_item)

    if initial_key:
        state["queue"].put(initial_item)
        state["queued_users"].add(initial_key)

    batch_to_save = []
    state["start_time"] = datetime.datetime.now()
    state["batch_counter"] = 0
    state["current_processing_user_id"] = None

    empty_cycles = 0
    max_empty_cycles = 5

    # Free Api Limit: 1 request/second
    state["executor"] = ThreadPoolExecutor(max_workers=2)

    with lock:
        state["is_scraping"] = True

    while state["is_scraping"]:
        current_batch = []
        for _ in range(1):
            if not state["queue"].empty():
                try:
                    current = normalize_queue_item(state["queue"].get_nowait())
                    current_key = get_queue_key(current)
                    if current_key:
                        state["queued_users"].discard(current_key)

                    current_sec_uid = current.get("sec_uid")

                    if current_sec_uid and (current_sec_uid in state["processed"] or current_sec_uid in global_processed_users):
                        state["skipped_count"] += 1
                        state["logs"].append({
                            "type": "info",
                            "message": f" Daha önce incelenmiş, atlandı: secUid={current_sec_uid[:25]}...",
                            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                        })
                        continue

                    if current.get("user_id"):
                        current_batch.append(current)
                except:
                    break
            else:
                break

        if not current_batch:
            empty_cycles += 1

            if empty_cycles >= max_empty_cycles:
                state["logs"].append({
                    "type": "info",
                    "message": f" Yeni kullanıcı bekleniyor... ({empty_cycles} boş döngü)",
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                })
                time.sleep(2)
                empty_cycles = 0
                continue
            else:
                time.sleep(1)
                continue

        empty_cycles = 0

        future_to_user = {
            state["executor"].submit(process_single_user, current, username, filters): current
            for current in current_batch
        }

        for future in as_completed(future_to_user):
            current = future_to_user[future]
            state["current_processing_user_id"] = current.get("user_id")

            try:
                result = future.result()

                if not result or len(result) < 2:
                    continue

                result_type = result[0]
                current_sec_uid = None

                if result_type == "already_processed":
                    if len(result) >= 3:
                        current_sec_uid = result[2]
                    if current_sec_uid:
                        state["processed"].add(current_sec_uid)
                        batch_to_save.append(current_sec_uid)
                    continue

                elif result_type == "rate_limited":
                    if len(result) > 1:
                        for error_log in result[1]:
                            state["logs"].append(error_log)

                    queue_key = get_queue_key(current)
                    if queue_key and queue_key not in state["queued_users"]:
                        state["queue"].put(current)
                        state["queued_users"].add(queue_key)

                    state["rate_limit_waits"] += 1
                    state["logs"].append({
                        "type": "warning",
                        "message": f" Rate limit bekleme uygulandı, kullanıcı tekrar kuyruğa alındı: user_id={current.get('user_id')}",
                        "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                    })
                    time.sleep(2.2)
                    continue

                elif result_type in ["json_error", "no_data", "general_error"]:
                    if len(result) > 1:
                        for error_log in result[1]:
                            state["logs"].append(error_log)

                    if len(result) >= 3:
                        current_sec_uid = result[2]
                    if current_sec_uid:
                        state["processed"].add(current_sec_uid)
                        batch_to_save.append(current_sec_uid)

                elif result_type == "success" and len(result) >= 4:
                    _, logs, new_users, current_sec_uid = result

                    for log_entry in logs:
                        state["logs"].append(log_entry)

                        if not log_entry.get("is_duplicate", False):
                            if len(state["recent_users"]) >= 10:
                                state["recent_users"].pop(0)
                            state["recent_users"].append({
                                "username": log_entry.get("username"),
                                "email": log_entry.get("email"),
                                "followers": log_entry.get("followers"),
                                "verified": log_entry.get("verified"),
                                "ttseller": log_entry.get("ttseller"),
                                "timestamp": log_entry.get("timestamp"),
                                "user_id": log_entry.get("user_id"),
                                "sec_uid": log_entry.get("sec_uid"),
                                "region": log_entry.get("region")
                            })

                    new_added = 0
                    for new_user in new_users:
                        new_user = normalize_queue_item(new_user)
                        new_key = get_queue_key(new_user)
                        new_sec_uid = new_user.get("sec_uid")

                        if (
                            new_key
                            and new_key not in state["queued_users"]
                            and (not new_sec_uid or (new_sec_uid not in state["processed"] and new_sec_uid not in global_processed_users))
                        ):
                            state["queue"].put(new_user)
                            state["queued_users"].add(new_key)
                            new_added += 1

                    if new_added > 0:
                        state["logs"].append({
                            "type": "info",
                            "message": f" {new_added} yeni kullanıcı kuyruğa eklendi",
                            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                        })

                    if current_sec_uid:
                        state["processed"].add(current_sec_uid)
                        batch_to_save.append(current_sec_uid)

                state["batch_counter"] += 1

                if state["batch_counter"] >= SAVE_BATCH_SIZE:
                    save_processed_users_batch(batch_to_save)
                    batch_to_save.clear()
                    state["batch_counter"] = 0

                    state["logs"].append({
                        "type": "info",
                        "message": f" {SAVE_BATCH_SIZE} kullanıcı dosyaya kaydedildi",
                        "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                    })

            except Exception as e:
                state["logs"].append({
                    "type": "error",
                    "message": f" İşlem hatası: user_id={current.get('user_id')} | {str(e)}",
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                })
            finally:
                state["current_processing_user_id"] = None

        time.sleep(random.uniform(1.3, 1.8))

    if batch_to_save:
        save_processed_users_batch(batch_to_save)
        state["logs"].append({
            "type": "info",
            "message": f" Son {len(batch_to_save)} kullanıcı dosyaya kaydedildi",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
        })

    if state["executor"]:
        state["executor"].shutdown(wait=True)
        state["executor"] = None

    with lock:
        state["is_scraping"] = False

    state["current_processing_user_id"] = None
    finish_scrape_session(username)
    save_user_states()


@app.route("/stop_scraper", methods=["POST"])
def stop_scraper():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    username = get_current_username()
    state = user_states[username]
    state["is_scraping"] = False

    if state["executor"]:
        state["executor"].shutdown(wait=False)
        state["executor"] = None

    state["current_processing_user_id"] = None
    finish_scrape_session(username)
    save_user_states()
    return jsonify({"message": "Veri toplama durduruldu."})


@app.route("/get_logs")
def get_logs():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    username = get_current_username()
    logs = user_states[username]["logs"]
    return jsonify({"logs": logs[-100:]})


@app.route("/get_mail_logs")
def get_mail_logs():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    username = get_current_username()
    mail_logs = user_states[username]["mail_logs"]
    return jsonify({"logs": mail_logs})


@app.route("/get_stats")
def get_stats():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    username = get_current_username()
    reset_user_usage_if_needed(username)

    state = user_states[username]
    logs = state["logs"]
    processed = state["processed"]
    queue_size = state["queue"].qsize()

    unique_emails = len(state["unique_emails"])
    shop_emails = set()
    normal_emails = set()

    for log in logs:
        if log.get("email") and not log.get("is_duplicate", False):
            if log.get("is_shop"):
                shop_emails.add(log["email"])
            else:
                normal_emails.add(log["email"])

    elapsed_time = ""
    if state["start_time"]:
        elapsed = datetime.datetime.now() - state["start_time"]
        hours, remainder = divmod(elapsed.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        elapsed_time = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

    user_info = USERS.get(username, {})
    return jsonify({
        "total": len(logs),
        "verified": sum(1 for log in logs if log.get("verified")),
        "unverified": sum(1 for log in logs if not log.get("verified")),
        "inprocess": queue_size,
        "checked": len(processed),
        "emails": unique_emails,
        "shop_emails": len(shop_emails),
        "normal_emails": len(normal_emails),
        "is_scraping": state["is_scraping"],
        "elapsed_time": elapsed_time,
        "recent_users": state["recent_users"][-10:],
        "filters": state["filters"],
        "results_count": len(state["results"]),
        "current_processing_user_id": state["current_processing_user_id"],
        "skipped_count": state["skipped_count"],
        "rate_limit_waits": state["rate_limit_waits"],
        "daily_scrape_used": safe_int(user_info.get("daily_scrape_used", 0)),
        "daily_scrape_limit": safe_int(user_info.get("daily_scrape_limit", 0)),
        "total_scrape_used": safe_int(user_info.get("total_scrape_used", 0)),
        "total_scrape_limit": safe_int(user_info.get("total_scrape_limit", 0)),
        "daily_export_count": safe_int(user_info.get("daily_export_count", 0)),
        "total_export_count": safe_int(user_info.get("total_export_count", 0)),
        "daily_mail_found": safe_int(user_info.get("daily_mail_found", 0)),
        "total_mail_found": safe_int(user_info.get("total_mail_found", 0)),
        "package_type": user_info.get("package_type", "trial"),
        "account_type": user_info.get("account_type", "trial"),
        "is_frozen": bool(user_info.get("is_frozen", False)),
        "total_active_seconds": safe_int(user_info.get("total_active_seconds", 0)),
        "total_active_time": format_duration(user_info.get("total_active_seconds", 0))
    })


@app.route("/get_region_analysis")
def get_region_analysis():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    username = get_current_username()
    state = user_states[username]
    analysis = build_region_analysis(state["results"])
    return jsonify(analysis)


@app.route("/get_chart_data")
def get_chart_data():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    username = get_current_username()
    state = user_states[username]
    return jsonify(build_chart_data(state["results"]))


@app.route("/get_queue_status")
def get_queue_status():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    username = get_current_username()
    state = user_states[username]

    next_items = snapshot_queue(state["queue"], limit=10)

    return jsonify({
        "queue_size": state["queue"].qsize(),
        "current_processing_user_id": state["current_processing_user_id"],
        "next_users": next_items,
        "skipped_count": state["skipped_count"],
        "rate_limit_waits": state["rate_limit_waits"],
        "is_scraping": state["is_scraping"]
    })


@app.route("/get_results")
def get_results():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    username = get_current_username()
    state = user_states[username]

    page = safe_int(request.args.get("page", 1), 1)
    per_page = safe_int(request.args.get("per_page", 50), 50)
    if per_page < 1:
        per_page = 50
    if per_page > 500:
        per_page = 500

    filtered = filter_results_list(state["results"], request.args)
    filtered = list(reversed(filtered))

    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    rows = filtered[start:end]

    return jsonify({
        "rows": rows,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page else 1
    })


@app.route("/export_results")
def export_results():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    username = get_current_username()
    if USERS.get(username, {}).get("is_frozen"):
        return jsonify({"error": "Hesap dondurulmuş."}), 403

    increment_export_usage(username, 1)

    state = user_states[username]
    export_format = str(request.args.get("format", "xlsx")).lower()
    filtered = filter_results_list(state["results"], request.args)

    rows = []
    for item in filtered:
        rows.append({
            "Username": item.get("username", ""),
            "Email": item.get("email", ""),
            "Followers": item.get("followers_raw", 0),
            "FollowersFormatted": item.get("followers", ""),
            "Region": item.get("region", ""),
            "Verified": "Yes" if item.get("verified") else "No",
            "Shop": "Yes" if item.get("is_shop") else "No",
            "UserID": item.get("user_id", ""),
            "SecUID": item.get("sec_uid", ""),
            "Bio": item.get("signature", ""),
            "Timestamp": item.get("timestamp", "")
        })

    filename_base = f"results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if export_format == "json":
        return jsonify({"rows": rows, "count": len(rows)})

    if export_format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()) if rows else [
            "Username", "Email", "Followers", "FollowersFormatted", "Region",
            "Verified", "Shop", "UserID", "SecUID", "Bio", "Timestamp"
        ])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

        mem = io.BytesIO()
        mem.write(output.getvalue().encode("utf-8-sig"))
        mem.seek(0)
        return send_file(
            mem,
            as_attachment=True,
            download_name=f"{filename_base}.csv",
            mimetype="text/csv"
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "Results"

    headers = list(rows[0].keys()) if rows else [
        "Username", "Email", "Followers", "FollowersFormatted", "Region",
        "Verified", "Shop", "UserID", "SecUID", "Bio", "Timestamp"
    ]
    ws.append(headers)

    for row in rows:
        ws.append([row.get(h, "") for h in headers])

    mem = io.BytesIO()
    wb.save(mem)
    mem.seek(0)

    return send_file(
        mem,
        as_attachment=True,
        download_name=f"{filename_base}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/clear_logs", methods=["POST"])
def clear_logs():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    username = get_current_username()
    with lock:
        user_states[username]["logs"] = []
        user_states[username]["mail_logs"] = []
        user_states[username]["recent_users"] = []
        user_states[username]["unique_emails"] = set()
        user_states[username]["result_keys"] = set()
        user_states[username]["results"] = []
        user_states[username]["skipped_count"] = 0
        user_states[username]["rate_limit_waits"] = 0
    save_user_states()
    return jsonify({"success": True, "message": "Loglar ve sonuçlar temizlendi."})


@app.route("/send_mail", methods=["POST"])
def send_mail():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    username = get_current_username()
    if USERS.get(username, {}).get("is_frozen"):
        return jsonify({"error": "Hesap dondurulmuş."}), 403

    state = user_states[username]
    data = request.json

    try:
        server = smtplib.SMTP_SSL(data["host"], int(data["port"]))
        server.login(data["user"], data["pass"])

        success_count = 0
        for r in data["recipients"]:
            try:
                username_email = r.get("username", "")
                email = r["email"]
                msg = MIMEMultipart()
                msg["From"] = data["from"]
                msg["To"] = email
                msg["Subject"] = data["subject"]

                html = data["html"].replace("@!username", f"@{username_email}")
                msg.attach(MIMEText(html, "html"))

                server.sendmail(data["from"], email, msg.as_string())
                state["mail_logs"].append({
                    "type": "success",
                    "message": f"? Gönderildi: {email}",
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                })
                success_count += 1
                time.sleep(data["delay"] / 1000)
            except Exception as e:
                state["mail_logs"].append({
                    "type": "error",
                    "message": f"? Hata: {email} - {str(e)}",
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                })

        server.quit()
        save_user_states()
        return jsonify({"status": "ok", "count": success_count})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/get_user_id", methods=["POST"])
def get_user_id():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    data = request.get_json()
    username_input = data.get("username")
    if not username_input:
        return jsonify({"error": "Kullanıcı adı girilmedi"}), 400

    try:
        res = requester.make_request(f"https://www.tiktok.com/@{username_input}", timeout=13)
        user_id, sec_uid = extract_user_id_and_secuid_from_profile_html(res.text)

        if not user_id:
            return jsonify({"error": "userId bulunamadı"}), 404

        if sec_uid and sec_uid in global_processed_users:
            return jsonify({"error": "Bu kullanıcı daha önce incelenmiş", "userId": user_id, "secUid": sec_uid}), 400

        return jsonify({"userId": user_id, "secUid": sec_uid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/get_secu_id", methods=["POST"])
def get_secu_id():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    data = request.get_json()
    username_input = data.get("username")
    if not username_input:
        return jsonify({"error": "Kullanıcı adı girilmedi"}), 400

    try:
        res = requester.make_request(f"https://www.tiktok.com/@{username_input}", timeout=13)
        user_id, sec_uid = extract_user_id_and_secuid_from_profile_html(res.text)

        if not user_id:
            return jsonify({"error": "userId bulunamadı"}), 404

        if sec_uid and sec_uid in global_processed_users:
            return jsonify({"error": "Bu kullanıcı daha önce incelenmiş"}), 400

        return jsonify({"userId": user_id, "secUid": sec_uid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/download_emails")
def download_emails():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    username = get_current_username()
    state = user_states[username]
    logs = state["logs"]
    email_type = request.args.get("type", "all")

    current_filter = state["filters"]["email_filter"]

    all_emails = []
    shop_emails = []
    normal_emails = []
    seen_emails = set()

    for log in logs:
        if log.get("email") and not log.get("is_duplicate", False):
            email = log["email"]
            if email not in seen_emails:
                seen_emails.add(email)

                if current_filter == "valid":
                    domain = email.split('@')[-1].lower()
                    if domain != "gmail.com":
                        continue

                email_data = f"{log.get('username', 'unknown')}:{email}"
                all_emails.append(email_data)

                if log.get("is_shop"):
                    shop_emails.append(email_data)
                else:
                    normal_emails.append(email_data)

    if email_type == "shop":
        return jsonify({"emails": shop_emails})
    elif email_type == "normal":
        return jsonify({"emails": normal_emails})
    else:
        return jsonify({"emails": all_emails})


@app.route("/get_users")
def get_users():
    global USERS
    if not is_user_authenticated() or session.get("role") != "admin":
        return jsonify({"error": "Yetkisiz erişim"}), 403

    users_list = []
    for username, data in USERS.items():
        data = ensure_user_record(username, data)
        reset_user_usage_if_needed(username)

        is_active = username in user_states and user_states[username]["is_scraping"]
        current_emails = len(user_states[username]["unique_emails"]) if username in user_states else 0

        users_list.append({
            "username": username,
            "role": data["role"],
            "created_at": data.get("created_at", "Bilinmiyor"),
            "last_login": data.get("last_login", "Hiç giriş yapmamış"),
            "last_login_device": data.get("last_login_device"),
            "is_active": is_active,
            "is_frozen": bool(data.get("is_frozen", False)),
            "package_type": data.get("package_type", "trial"),
            "account_type": data.get("account_type", "trial"),
            "daily_scrape_limit": safe_int(data.get("daily_scrape_limit", 0)),
            "total_scrape_limit": safe_int(data.get("total_scrape_limit", 0)),
            "daily_scrape_used": safe_int(data.get("daily_scrape_used", 0)),
            "total_scrape_used": safe_int(data.get("total_scrape_used", 0)),
            "daily_export_count": safe_int(data.get("daily_export_count", 0)),
            "total_export_count": safe_int(data.get("total_export_count", 0)),
            "daily_mail_found": safe_int(data.get("daily_mail_found", 0)),
            "total_mail_found": safe_int(data.get("total_mail_found", 0)),
            "total_active_seconds": safe_int(data.get("total_active_seconds", 0)),
            "total_active_time": format_duration(data.get("total_active_seconds", 0)),
            "current_emails_found": current_emails,
            "last_ip": data.get("last_ip")
        })

    save_users(USERS)
    return jsonify({"users": users_list})


@app.route("/add_user", methods=["POST"])
def add_user():
    global USERS
    if not is_user_authenticated() or session.get("role") != "admin":
        return jsonify({"error": "Yetkisiz erişim"}), 403

    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    role = data.get("role", "user")

    if not username or not password:
        return jsonify({"error": "Kullanıcı adı ve şifre gerekli"}), 400

    if username in USERS:
        return jsonify({"error": "Bu kullanıcı adı zaten mevcut"}), 400

    package_type = data.get("packageType", "trial")
    account_type = data.get("accountType", "trial")
    daily_scrape_limit = safe_int(data.get("dailyScrapeLimit", 50 if role != "admin" else 999999), 50 if role != "admin" else 999999)
    total_scrape_limit = safe_int(data.get("totalScrapeLimit", 500 if role != "admin" else 999999999), 500 if role != "admin" else 999999999)
    is_frozen = bool(data.get("isFrozen", False))

    USERS[username] = {
        "password": password,
        **default_user_meta(role),
        "created_at": now_str(),
        "package_type": package_type,
        "account_type": account_type,
        "daily_scrape_limit": daily_scrape_limit,
        "total_scrape_limit": total_scrape_limit,
        "is_frozen": is_frozen
    }

    USERS[username] = ensure_user_record(username, USERS[username])

    save_users(USERS)
    return jsonify({"success": True, "message": "Kullanıcı başarıyla eklendi"})


@app.route("/update_user_plan", methods=["POST"])
def update_user_plan():
    global USERS
    if not is_user_authenticated() or session.get("role") != "admin":
        return jsonify({"error": "Yetkisiz erişim"}), 403

    data = request.get_json()
    username = data.get("username", "").strip()

    if not username or username not in USERS:
        return jsonify({"error": "Kullanıcı bulunamadı"}), 404

    USERS[username] = ensure_user_record(username, USERS[username])

    if "packageType" in data:
        USERS[username]["package_type"] = str(data.get("packageType") or "trial").strip()

    if "accountType" in data:
        USERS[username]["account_type"] = str(data.get("accountType") or "trial").strip()

    if "dailyScrapeLimit" in data:
        USERS[username]["daily_scrape_limit"] = safe_int(data.get("dailyScrapeLimit"), USERS[username]["daily_scrape_limit"])

    if "totalScrapeLimit" in data:
        USERS[username]["total_scrape_limit"] = safe_int(data.get("totalScrapeLimit"), USERS[username]["total_scrape_limit"])

    if "isFrozen" in data:
        USERS[username]["is_frozen"] = bool(data.get("isFrozen"))

    save_users(USERS)
    return jsonify({"success": True, "message": "Kullanıcı planı güncellendi"})


@app.route("/toggle_user_freeze", methods=["POST"])
def toggle_user_freeze():
    global USERS
    if not is_user_authenticated() or session.get("role") != "admin":
        return jsonify({"error": "Yetkisiz erişim"}), 403

    data = request.get_json()
    username = data.get("username", "").strip()

    if not username or username not in USERS:
        return jsonify({"error": "Kullanıcı bulunamadı"}), 404

    USERS[username] = ensure_user_record(username, USERS[username])
    USERS[username]["is_frozen"] = not bool(USERS[username].get("is_frozen", False))

    if USERS[username]["is_frozen"] and username in user_states:
        user_states[username]["is_scraping"] = False
        if user_states[username]["executor"]:
            user_states[username]["executor"].shutdown(wait=False)
            user_states[username]["executor"] = None
        user_states[username]["current_processing_user_id"] = None
        finish_scrape_session(username)

    save_users(USERS)
    save_user_states()

    return jsonify({
        "success": True,
        "message": f"{username} hesabı {'donduruldu' if USERS[username]['is_frozen'] else 'aktif edildi'}",
        "is_frozen": USERS[username]["is_frozen"]
    })


@app.route("/delete_user", methods=["POST"])
def delete_user():
    global USERS
    if not is_user_authenticated() or session.get("role") != "admin":
        return jsonify({"error": "Yetkisiz erişim"}), 403

    data = request.get_json()
    username = data.get("username")

    if not username:
        return jsonify({"error": "Kullanıcı adı gerekli"}), 400

    if username == "talha":
        return jsonify({"error": "Ana admin kullanıcısı silinemez"}), 400

    if username not in USERS:
        return jsonify({"error": "Kullanıcı bulunamadı"}), 404

    if username in user_states:
        user_states[username]["is_scraping"] = False
        if user_states[username]["executor"]:
            user_states[username]["executor"].shutdown(wait=False)
        del user_states[username]

    if username in SESSIONS:
        del SESSIONS[username]

    del USERS[username]
    save_users(USERS)
    save_user_states()
    return jsonify({"success": True, "message": "Kullanıcı başarıyla silindi"})


@app.route("/get_user_emails")
def get_user_emails():
    if not is_user_authenticated() or session.get("role") != "admin":
        return jsonify({"error": "Yetkisiz erişim"}), 403

    target_username = request.args.get("username")
    if not target_username:
        return jsonify({"error": "Kullanıcı adı gerekli"}), 400

    if target_username in user_states:
        state = user_states[target_username]
        logs = state["logs"]
        current_filter = state["filters"]["email_filter"]
        emails = []
        seen_emails = set()

        for log in logs:
            if log.get("email") and not log.get("is_duplicate", False):
                email = log["email"]
                if email not in seen_emails:
                    seen_emails.add(email)

                    if current_filter == "valid":
                        domain = email.split('@')[-1].lower()
                        if domain != "gmail.com":
                            continue

                    emails.append({
                        "username": log.get("username"),
                        "email": email,
                        "followers": log.get("followers"),
                        "verified": log.get("verified"),
                        "ttseller": log.get("ttseller"),
                        "timestamp": log.get("timestamp"),
                        "user_id": log.get("user_id"),
                        "sec_uid": log.get("sec_uid"),
                        "region": log.get("region")
                    })
        return jsonify({"emails": emails})

    return jsonify({"emails": [], "message": "Kullanıcı verisi bulunamadı"})


@app.route("/get_user_stats")
def get_user_stats():
    global USERS
    if not is_user_authenticated() or session.get("role") != "admin":
        return jsonify({"error": "Oturum geçersiz"}), 401

    target_username = request.args.get("username")
    if not target_username:
        return jsonify({"error": "Kullanıcı adı gerekli"}), 400

    if target_username in USERS:
        USERS[target_username] = ensure_user_record(target_username, USERS[target_username])
        reset_user_usage_if_needed(target_username)

    if target_username in user_states:
        state = user_states[target_username]
        logs = state["logs"]
        processed = state["processed"]
        queue_size = state["queue"].qsize()

        unique_emails = len(state["unique_emails"])
        shop_emails = set()
        normal_emails = set()

        for log in logs:
            if log.get("email") and not log.get("is_duplicate", False):
                if log.get("is_shop"):
                    shop_emails.add(log["email"])
                else:
                    normal_emails.add(log["email"])

        elapsed_time = ""
        if state["start_time"]:
            elapsed = datetime.datetime.now() - state["start_time"]
            hours, remainder = divmod(elapsed.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            elapsed_time = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

        user_info = USERS.get(target_username, {})
        return jsonify({
            "total": len(logs),
            "verified": sum(1 for log in logs if log.get("verified")),
            "unverified": sum(1 for log in logs if not log.get("verified")),
            "inprocess": queue_size,
            "checked": len(processed),
            "emails": unique_emails,
            "shop_emails": len(shop_emails),
            "normal_emails": len(normal_emails),
            "is_scraping": state["is_scraping"],
            "elapsed_time": elapsed_time,
            "recent_users": state["recent_users"][-10:],
            "filters": state["filters"],
            "results_count": len(state["results"]),
            "current_processing_user_id": state["current_processing_user_id"],
            "skipped_count": state["skipped_count"],
            "rate_limit_waits": state["rate_limit_waits"],
            "daily_scrape_used": safe_int(user_info.get("daily_scrape_used", 0)),
            "daily_scrape_limit": safe_int(user_info.get("daily_scrape_limit", 0)),
            "total_scrape_used": safe_int(user_info.get("total_scrape_used", 0)),
            "total_scrape_limit": safe_int(user_info.get("total_scrape_limit", 0)),
            "daily_export_count": safe_int(user_info.get("daily_export_count", 0)),
            "total_export_count": safe_int(user_info.get("total_export_count", 0)),
            "daily_mail_found": safe_int(user_info.get("daily_mail_found", 0)),
            "total_mail_found": safe_int(user_info.get("total_mail_found", 0)),
            "package_type": user_info.get("package_type", "trial"),
            "account_type": user_info.get("account_type", "trial"),
            "is_frozen": bool(user_info.get("is_frozen", False)),
            "last_login_device": user_info.get("last_login_device"),
            "total_active_seconds": safe_int(user_info.get("total_active_seconds", 0)),
            "total_active_time": format_duration(user_info.get("total_active_seconds", 0))
        })

    return jsonify({"error": "Kullanıcı verisi bulunamadı"}), 404


@app.route("/get_blocked_ips")
def get_blocked_ips():
    if not is_user_authenticated() or session.get("role") != "admin":
        return jsonify({"error": "Yetkisiz erişim"}), 403

    return jsonify({"blocked_ips": list(BLOCKED_IPS)})


@app.route("/block_ip", methods=["POST"])
def block_ip():
    if not is_user_authenticated() or session.get("role") != "admin":
        return jsonify({"error": "Yetkisiz erişim"}), 403

    data = request.get_json()
    ip = data.get("ip", "").strip()

    if not ip:
        return jsonify({"error": "IP adresi gerekli"}), 400

    if ip in ["127.0.0.1", "localhost"]:
        return jsonify({"error": "Localhost engellenemez"}), 400

    BLOCKED_IPS.add(ip)
    return jsonify({"success": True, "message": f"IP {ip} engellendi"})


@app.route("/unblock_ip", methods=["POST"])
def unblock_ip():
    if not is_user_authenticated() or session.get("role") != "admin":
        return jsonify({"error": "Yetkisiz erişim"}), 403

    data = request.get_json()
    ip = data.get("ip", "").strip()

    if not ip:
        return jsonify({"error": "IP adresi gerekli"}), 400

    BLOCKED_IPS.discard(ip)
    return jsonify({"success": True, "message": f"IP {ip} engeli kaldırıldı"})


@app.route("/stop_user_scraper", methods=["POST"])
def stop_user_scraper():
    if not is_user_authenticated() or session.get("role") != "admin":
        return jsonify({"error": "Yetkisiz erişim"}), 403

    data = request.get_json()
    target_username = data.get("username")

    if not target_username:
        return jsonify({"error": "Kullanıcı adı gerekli"}), 400

    if target_username in user_states:
        user_states[target_username]["is_scraping"] = False
        if user_states[target_username]["executor"]:
            user_states[target_username]["executor"].shutdown(wait=False)
            user_states[target_username]["executor"] = None
        user_states[target_username]["current_processing_user_id"] = None
        finish_scrape_session(target_username)
        save_user_states()
        return jsonify({"success": True, "message": f"{target_username} kullanıcısının işlemi durduruldu"})

    return jsonify({"error": "Kullanıcı bulunamadı"}), 404


@app.route("/clear_user_logs", methods=["POST"])
def clear_user_logs():
    if not is_user_authenticated() or session.get("role") != "admin":
        return jsonify({"error": "Yetkisiz erişim"}), 403

    data = request.get_json()
    target_username = data.get("username")

    if not target_username:
        return jsonify({"error": "Kullanıcı adı gerekli"}), 400

    if target_username in user_states:
        with lock:
            user_states[target_username]["logs"] = []
            user_states[target_username]["mail_logs"] = []
            user_states[target_username]["recent_users"] = []
            user_states[target_username]["unique_emails"] = set()
            user_states[target_username]["result_keys"] = set()
            user_states[target_username]["results"] = []
            user_states[target_username]["skipped_count"] = 0
            user_states[target_username]["rate_limit_waits"] = 0
        save_user_states()
        return jsonify({"success": True, "message": f"{target_username} kullanıcısının logları temizlendi"})

    return jsonify({"error": "Kullanıcı bulunamadı"}), 404


@app.route("/get_system_stats")
def get_system_stats():
    global USERS
    if not is_user_authenticated() or session.get("role") != "admin":
        return jsonify({"error": "Yetkisiz erişim"}), 403

    active_users = 0
    total_emails = 0
    total_processed = 0
    total_results = 0
    frozen_users = 0
    premium_users = 0
    trial_users = 0
    total_exports = 0
    total_active_seconds = 0

    for username, data in USERS.items():
        data = ensure_user_record(username, data)
        reset_user_usage_if_needed(username)

        if data.get("is_frozen"):
            frozen_users += 1

        if data.get("account_type") == "premium":
            premium_users += 1
        else:
            trial_users += 1

        total_exports += safe_int(data.get("total_export_count", 0))
        total_active_seconds += safe_int(data.get("total_active_seconds", 0))

    for username, state in user_states.items():
        if state["is_scraping"]:
            active_users += 1

        total_emails += len(state["unique_emails"])
        total_processed += len(state["processed"])
        total_results += len(state["results"])

    try:
        with open(PROCESSED_USERS_FILE, "r", encoding='utf-8') as f:
            file_processed = len([line for line in f.read().strip().splitlines() if line.strip()])
    except:
        file_processed = 0

    save_users(USERS)

    return jsonify({
        "active_users": active_users,
        "total_users": len(USERS),
        "frozen_users": frozen_users,
        "premium_users": premium_users,
        "trial_users": trial_users,
        "total_emails_found": total_emails,
        "total_processed_by_users": total_processed,
        "total_processed_global": file_processed,
        "total_results": total_results,
        "blocked_ips": len(BLOCKED_IPS),
        "total_exports": total_exports,
        "total_active_seconds": total_active_seconds,
        "total_active_time": format_duration(total_active_seconds)
    })


@app.route("/check_scraper_status")
def check_scraper_status():
    if not is_user_authenticated():
        return jsonify({"error": "Oturum geçersiz"}), 401

    username = get_current_username()
    reset_user_usage_if_needed(username)
    state = user_states[username]
    user_info = USERS.get(username, {})

    return jsonify({
        "is_scraping": state["is_scraping"],
        "has_data": len(state["logs"]) > 0,
        "filters": state["filters"],
        "current_processing_user_id": state["current_processing_user_id"],
        "skipped_count": state["skipped_count"],
        "rate_limit_waits": state["rate_limit_waits"],
        "is_frozen": bool(user_info.get("is_frozen", False)),
        "package_type": user_info.get("package_type", "trial"),
        "account_type": user_info.get("account_type", "trial"),
        "daily_scrape_used": safe_int(user_info.get("daily_scrape_used", 0)),
        "daily_scrape_limit": safe_int(user_info.get("daily_scrape_limit", 0)),
        "daily_export_count": safe_int(user_info.get("daily_export_count", 0)),
        "total_export_count": safe_int(user_info.get("total_export_count", 0))
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=False, threaded=True)