import os
import random
import time
import requests
import execjs
import json
import pandas as pd
from urllib.parse import quote_plus
from requests import RequestException

# =========================
# Config
# =========================
KEYWORD = "NIO"          # search keyword
TARGET_COUNT = 100
OUTPUT_XLSX = f"{KEYWORD}_xiaohongshu.xlsx"

base_headers = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "content-type": "application/json;charset=UTF-8",
    "dnt": "1",
    "origin": "https://www.xiaohongshu.com",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "referer": "https://www.xiaohongshu.com/",
    "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "xsecappid": "xhs-pc-web",
    # ---- Paste a fresh cookie value from a logged-in request to edith.xiaohongshu.com ----
    "cookie": "abRequestId=f14c925e-94af-5f3c-af5d-7d018218ac90; a1=19847abd0a1pyj01p1sqj5y3ckyd8h8csu3xdm27030000321205; webId=b08c4e1d2e21e627bad120937f526882; gid=yjY4W0Di2yM4yjY4W0Df876J0yUvV8yUyMAVqW82vqSTvCq8fYxYSf888qJyJ82840Sq4jKj; webBuild=4.74.3; acw_tc=0a00d2d717537675310654277e225a5a03d8c8633e070071cfe420c377620d; xsecappid=xhs-pc-web; loadts=1753768227856; web_session=040069720f1aedd9fa8b5529bd3a4bb185b72f; websectiga=f47eda31ec99545da40c2f731f0630efd2b0959e1dd10d5fedac3dce0bd1e04d; sec_poison_id=f716b0aa-ad1b-49d9-9138-9568545f02c6; unread={%22ub%22:%2268883f90000000002400c312%22%2C%22ue%22:%22688614bb000000001d00ff0a%22%2C%22uc%22:9}",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

# Globals
rows = []
note_count = 0
xhs_sign_obj = None

XHS_HOME = "https://www.xiaohongshu.com"
NOTE_LINK_TMPL = XHS_HOME + "/explore/{note_id}?xsec_token={xsec}&xsec_source=pc_search"
USER_LINK_TMPL = XHS_HOME + "/user/profile/{user_id}"

# =========================
# HTTP + signing
# =========================
def post_request(url, uri, data, max_retries=5, delay=5):
    """POST with signed headers; basic retries."""
    sign_header = xhs_sign_obj.call("sign", uri, data, base_headers.get("cookie", ""))
    headers = {**base_headers, **sign_header}
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, data=payload.encode("utf-8"), timeout=15)
            return resp
        except RequestException:
            if attempt < max_retries - 1:
                print("Request error, retrying...")
                time.sleep(delay)
            else:
                print("Request failed. Refresh cookie or try another account.")
    return None

# =========================
# Utilities
# =========================
def format_time_from_ms(ms):
    try:
        ts = int(ms) / 1000
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    except Exception:
        return ""

def clean_text(s):
    return (s or "").replace("\r", " ").replace("\n", " ").strip()

def join_urls(urls):
    urls = [u for u in urls if u]
    return " | ".join(urls)

def extract_image_urls(note_card: dict):
    urls = []
    for img in (note_card.get("image_list") or []):
        cand = img.get("url") or img.get("img_url") or img.get("image_url") or ""
        if not cand:
            for k in ("urls", "url_list"):
                if k in img and isinstance(img[k], list) and img[k]:
                    cand = img[k][0]
                    break
        if cand:
            urls.append(cand)
    if not urls:
        cover = note_card.get("cover") or {}
        if isinstance(cover, dict):
            cand = cover.get("url") or cover.get("image_url") or ""
            if cand:
                urls.append(cand)
    # de-duplicate
    return list(dict.fromkeys(urls))

def extract_video_urls(note_card: dict):
    v = note_card.get("video") or note_card.get("note_video") or {}
    if not isinstance(v, dict):
        return []
    urls = []
    direct = v.get("url") or v.get("play_url") or v.get("master_url")
    if direct:
        urls.append(direct)
    for chain in [
        ("url_list",),
        ("h264", "url_list"),
        ("play_addr", "url_list"),
        ("media", "dash", "play_addr", "url_list"),
        ("media", "stream", "h264", "url_list"),
        ("media", "stream", "url_list"),
    ]:
        ref, ok = v, True
        for k in chain:
            ref = ref.get(k) if isinstance(ref, dict) else None
            if ref is None:
                ok = False
                break
        if ok and isinstance(ref, list):
            urls.extend(ref)
    # de-duplicate
    seen, out = set(), []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out

# =========================
# Data pipeline
# =========================
def append_row_from_note(note_data, note_id, xsec_token):
    global note_count, rows

    card = note_data["note_card"]
    user = card.get("user", {}) or {}
    inter = card.get("interact_info", {}) or {}

    record = {
        "Post URL": NOTE_LINK_TMPL.format(note_id=note_id, xsec=xsec_token),
        "Author Name": clean_text(user.get("nickname")),
        # Keep aligned with your working template: read directly from interact_info
        "Likes": inter.get("liked_count"),
        "Comments": inter.get("comment_count"),
        "Post Title": clean_text(card.get("title")),
        "Caption": clean_text(card.get("desc")),
        "Date Published": format_time_from_ms(card.get("time", 0)),
        "Video URL": join_urls(extract_video_urls(card)),
        "User URL": USER_LINK_TMPL.format(user_id=clean_text(user.get("user_id"))) if user.get("user_id") else "",
        "Images URL": join_urls(extract_image_urls(card)),
    }

    note_count += 1
    rows.append(record)
    print(f"[{note_count}] {record['Post Title'][:60]}  likes={record['Likes']}  comments={record['Comments']}")

def fetch_note_detail(note_id, xsec_token):
    url = "https://edith.xiaohongshu.com/api/sns/web/v1/feed"
    data = {
        "source_note_id": note_id,
        "image_scenes": ["jpg", "webp", "avif"],
        "extra": {"need_body_topic": "1"},
        "xsec_token": xsec_token,
        "xsec_source": "pc_search"
    }
    resp = post_request(url, uri="/api/sns/web/v1/feed", data=data)
    if not resp or resp.status_code != 200:
        print(f"Note {note_id} request failed.")
        return
    jd = resp.json()
    try:
        note_data = jd["data"]["items"][0]
    except Exception:
        print(f"Note {note_id} is not viewable or could not be parsed.")
        return
    append_row_from_note(note_data, note_id, xsec_token)

def search_keyword(keyword):
    search_url = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"
    page = 1
    while len(rows) < TARGET_COUNT:
        data = {
            "ext_flags": [],
            "image_formats": ["jpg", "webp", "avif"],
            "keyword": keyword,
            "note_type": 0,
            "page": page,
            "page_size": 20,
            "search_id": xhs_sign_obj.call("searchId"),
            # Keep aligned with the original: 'general'
            "sort": "general"
        }
        base_headers["referer"] = f"https://www.xiaohongshu.com/search_result?keyword={quote_plus(keyword)}"

        resp = post_request(search_url, uri="/api/sns/web/v1/search/notes", data=data)
        if not resp or resp.status_code != 200:
            print("Search API error. Stopping.")
            break

        jd = resp.json()
        items = (jd.get("data") or {}).get("items") or []
        print(f"search page={page} items={len(items)}")

        if not items:
            print("No more results.")
            break

        for note in items:
            if len(rows) >= TARGET_COUNT:
                break
            note_id = note.get("id", "")
            xsec_token = note.get("xsec_token", "")
            if not note_id or len(note_id) != 24:
                continue
            fetch_note_detail(note_id, xsec_token)
            time.sleep(random.uniform(0.35, 0.8))  # polite delay

        page += 1
        time.sleep(random.uniform(0.8, 1.5))      # page delay

# =========================
# Main
# =========================
if __name__ == "__main__":
    # Load signer from the same folder as this script
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    XHS_JS_PATH = os.path.join(SCRIPT_DIR, "xhs.js")
    with open(XHS_JS_PATH, encoding="utf-8") as f:
        xhs_sign_obj = execjs.compile(f.read())

    print(f"Searching '{KEYWORD}' with target {TARGET_COUNT} posts...")
    search_keyword(KEYWORD)

    # Save to Excel
    df = pd.DataFrame(rows, columns=[
        "Post URL",
        "Author Name",
        "Likes",
        "Comments",
        "Post Title",
        "Caption",
        "Date Published",
        "Video URL",
        "User URL",
        "Images URL",
    ])
    out_path = os.path.join(SCRIPT_DIR, OUTPUT_XLSX)
    df.to_excel(out_path, index=False)
    print(f"\nDone. Exported {len(df)} rows to {OUTPUT_XLSX}")
