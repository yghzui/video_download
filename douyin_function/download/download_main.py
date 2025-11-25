import os
import re
import json
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
import threading
import csv
from datetime import datetime, timedelta
import sys
import shutil
import subprocess

PATTERNS = [
    re.compile(r'https://(.*?).douyin.com/aweme/v1/web/aweme/post/'),
    re.compile(r'https://www.douyin.com/aweme/v1/web/general/search/single/'),
    re.compile(r'https://www.douyin.com/aweme/v1/web/aweme/detail/'),
    re.compile(r'https://www.douyin.com/aweme/v1/web/aweme/favorite/'),
    re.compile(r'https://www.douyin.com/aweme/v1/web/aweme/listcollection/')
]

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

def safe(s):
    return s.replace('\n',' ').replace('(', '（').replace(')', '）').replace(':', '：').replace('*', '＊').replace('?', '？').replace('"', '＂').replace('<', '＜').replace('>', '＞').replace('|', '｜').replace('\\', '＼').replace('/', '／')

def format_name(fmt, item, index):
    s = fmt.replace('{标题}', item.get('title') or '')\
        .replace('{id}', str(item.get('id') or ''))\
        .replace('{发布者}', item.get('author_name') or '')\
        .replace('{抖音号}', item.get('author_handle') or '')\
        .replace('{时间}', item.get('publish_time') or '')\
        .replace('{i}', str(index))
    return safe(s)

def parse_cookie_file(path):
    if not os.path.exists(path):
        return '', []
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    header = data.get('cookie_header') or ''
    cookies = []
    for part in header.split(';'):
        part = part.strip()
        if not part or '=' not in part:
            continue
        name, value = part.split('=', 1)
        lname = name.lower()
        if lname in ['path', 'domain', 'expires', 'max-age', 'samesite', 'httponly', 'secure']:
            continue
        if name.strip().lower() == 'douyin.com':
            continue
        cookies.append({'name': name.strip(), 'value': value, 'domain': 'douyin.com', 'path': '/'})
    return header, cookies

def parse_douyin_item(data, host_index=1):
    video = data.get('video') or {}
    author = data.get('author') or data.get('authorInfo') or {}
    aweme_id = data.get('aweme_id') or data.get('awemeId')
    desc = data.get('desc') or ''
    images = data.get('images')
    cover = ((video.get('cover') or {}).get('url_list') or data.get('coverUrlList') or [''])[0] if isinstance(((video.get('cover') or {}).get('url_list') or data.get('coverUrlList')), list) else ''
    if images:
        arr = []
        for im in images:
            dl = im.get('download_url_list') or im.get('downloadUrlList') or []
            if dl:
                arr.append({'url': dl[0], 'type': 'photo'})
        urls = arr
    else:
        url_list = (video.get('play_addr') or {}).get('url_list') or []
        if url_list:
            urls = url_list[host_index] if host_index < len(url_list) else url_list[-1]
        else:
            urls = ''
    create_time = data.get('create_time') or data.get('createTime')
    publish_str = ''
    try:
        if isinstance(create_time, (int, float)):
            dt = datetime.utcfromtimestamp(int(create_time)) + timedelta(hours=8)
            publish_str = dt.strftime('%Y_%m_%d_%H_%M_%S')
    except Exception:
        publish_str = ''
    return {'id': aweme_id,
            'title': desc,
            'author_name': author.get('nickname') or '',
            'author_handle': author.get('unique_id') or author.get('uniqueId') or author.get('short_id') or '',
            'author_sec_uid': author.get('sec_uid') or author.get('uid') or author.get('unique_id') or author.get('uniqueId') or '',
            'author_id': author.get('uid') or '',
            'cover': cover,
            'urls': urls,
            'url': f'https://www.douyin.com/video/{aweme_id}',
            'publish_time': publish_str,
            'publish_ts': create_time}

def collect_items(page, host_index=1):
    items = []
    def handle_response(response):
        url = response.url
        if not any(p.search(url) for p in PATTERNS):
            return
        data = None
        try:
            data = response.json()
        except Exception:
            try:
                txt = response.text()
                data = json.loads(txt)
            except Exception:
                data = None
        if not data:
            return
        lists = []
        if isinstance(data, dict):
            if 'aweme_list' in data and isinstance(data['aweme_list'], list):
                lists = data['aweme_list']
            elif 'aweme_detail' in data:
                lists = [data['aweme_detail']]
            elif 'data' in data and isinstance(data['data'], list):
                lists = [x.get('aweme_info') for x in data['data'] if isinstance(x, dict) and x.get('aweme_info')]
            elif 'detail' in data:
                lists = [data['detail']]
        for d in lists:
            if not d:
                continue
            item = parse_douyin_item(d, host_index=host_index)
            if item.get('id') and not any(x['id'] == item['id'] for x in items):
                items.append(item)
    page.on('response', handle_response)
    return items

def autoscroll(page, items, max_idle=10, interval_ms=2000, container_selector='.route-scroll-container'):
    idle = 0
    last = 0
    while idle < max_idle:
        container = None
        try:
            container = page.query_selector(container_selector)
        except Exception:
            container = None
        if container:
            page.evaluate('el => el.scrollTop = el.scrollHeight', container)
        else:
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        time.sleep(max(0.001, interval_ms/1000.0))
        cur = len(items)
        if cur == last:
            idle += 1
        else:
            last = cur
            idle = 0

def download_requests(url, path, headers, retry):
    for i in range(retry + 1):
        try:
            with requests.get(url, headers=headers, stream=True, timeout=120) as r:
                if r.status_code in [200, 206]:
                    with open(path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1 << 20):
                            if chunk:
                                f.write(chunk)
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False

def download_aria2(url, name, save_dir, headers, host='127.0.0.1', port=6800, secret=''):
    rpc = f'http://{host}:{port}/jsonrpc'
    hdr = [f'{k}: {v}' for k, v in headers.items()]
    params = [[url], {'dir': save_dir, 'out': name, 'header': hdr}]
    if secret:
        params.insert(0, f'token:{secret}')
    payload = {'jsonrpc': '2.0', 'id': name, 'method': 'aria2.addUri', 'params': params}
    try:
        r = requests.post(rpc, json=payload, timeout=10)
        if r.status_code == 200:
            j = r.json()
            if 'result' in j and j['result']:
                return j['result']
    except Exception:
        pass
    return False

def human_bytes(n):
    units = ['B','KB','MB','GB','TB']
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units)-1:
        f /= 1024.0
        i += 1
    return f"{f:.2f}{units[i]}"

def build_jobs(items, save_dir, name_format):
    jobs = []
    idx = 0
    for it in items:
        urls = it['urls']
        if isinstance(urls, list):
            k = 0
            for u in urls:
                url = u['url'] if isinstance(u, dict) else str(u)
                jtype = 'photo' if isinstance(u, dict) and u.get('type') == 'photo' else 'video'
                ext = '.jpg' if jtype == 'photo' else '.mp4'
                idx += 1
                name = format_name(name_format, it, idx)
                if jtype == 'photo':
                    name_with_idx = f"{name}_{k+1}"
                else:
                    name_with_idx = name
                path = os.path.join(save_dir, name_with_idx + ext)
                key = f"{it.get('id') or ''}:{jtype}:{k}"
                jobs.append({'url': url, 'path': path, 'name': name_with_idx + ext, 'id': it.get('id'), 'title': it.get('title'), 'author': it.get('author_name'), 'author_handle': it.get('author_handle',''), 'author_sec_uid': it.get('author_sec_uid', ''), 'publish_time': it.get('publish_time',''), 'page_url': it.get('url'), 'type': jtype, 'seq': k, 'key': key})
                k += 1
        else:
            url = str(urls)
            jtype = 'video'
            ext = '.mp4'
            idx += 1
            name = format_name(name_format, it, idx)
            path = os.path.join(save_dir, name + ext)
            key = f"{it.get('id') or ''}:{jtype}:0"
            jobs.append({'url': url, 'path': path, 'name': name + ext, 'id': it.get('id'), 'title': it.get('title'), 'author': it.get('author_name'), 'author_handle': it.get('author_handle',''), 'author_sec_uid': it.get('author_sec_uid', ''), 'publish_time': it.get('publish_time',''), 'page_url': it.get('url'), 'type': jtype, 'seq': 0, 'key': key})
    return jobs

def read_history_map(history_path):
    if not os.path.exists(history_path):
        return {}, {}
    m_key = {}
    m_url = {}
    try:
        with open(history_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get('url')
                path = row.get('path')
                key = row.get('key')
                if key:
                    m_key[key] = path
                if url:
                    m_url[url] = path
    except Exception:
        pass
    return m_key, m_url

def append_history(history_path, row):
    head = ['timestamp', 'url', 'path', 'name', 'id', 'title', 'author', 'author_handle', 'publish_time', 'page_url', 'mode', 'bytes', 'status', 'key']
    exists = os.path.exists(history_path)
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    with open(history_path, 'a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=head)
        if not exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, '') for k in head})

def find_existing_by_id(save_dir, id_str):
    if not id_str:
        return None
    try:
        for root, _, files in os.walk(save_dir):
            for nm in files:
                if id_str in nm:
                    return os.path.join(root, nm)
    except Exception:
        return None
    return None

def extract_author_id(items, url_or_id):
    aid = ''
    for it in items:
        sec = it.get('author_sec_uid') or ''
        if sec:
            aid = sec
            break
    if not aid:
        if url_or_id and not url_or_id.startswith('http'):
            aid = url_or_id
        elif url_or_id and url_or_id.startswith('http'):
            try:
                from urllib.parse import urlparse
                p = urlparse(url_or_id)
                parts = [x for x in p.path.split('/') if x]
                if 'user' in parts:
                    i = parts.index('user')
                    if i + 1 < len(parts):
                        aid = parts[i+1].split('?')[0]
            except Exception:
                pass
    return aid

def extract_author_handle_from_dom(page):
    try:
        val = page.evaluate('''() => {
            const spans = Array.from(document.querySelectorAll('span'));
            for (const s of spans) {
                const t = (s.textContent || '').trim();
                if (t.includes('抖音号')) {
                    const m = t.match(/抖音号：\s*(\S+)/);
                    if (m && m[1]) return m[1];
                }
            }
            return '';
        }''')
        return val or ''
    except Exception:
        return ''

def ensure_project_chromium():
    base = os.path.abspath(os.path.join('douyin_function', 'vendor', 'chromium'))
    os.makedirs(base, exist_ok=True)
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = base
    def vendor_has_chrome():
        for root, dirs, files in os.walk(base):
            if os.path.basename(root).lower() == 'chrome-win':
                if os.path.exists(os.path.join(root, 'chrome.exe')):
                    return True
        return False
    if vendor_has_chrome():
        return
    copied = False
    local_ms = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ms-playwright')
    try:
        if os.path.isdir(local_ms):
            candidates = [d for d in os.listdir(local_ms) if d.startswith('chromium-')]
            candidates = sorted(candidates, key=lambda d: os.path.getmtime(os.path.join(local_ms, d)), reverse=True)
            if candidates:
                src = os.path.join(local_ms, candidates[0])
                dest = os.path.join(base, candidates[0])
                if not os.path.exists(dest):
                    shutil.copytree(src, dest)
                copied = True
    except Exception:
        copied = False
    if not copied:
        env = os.environ.copy()
        env['PLAYWRIGHT_BROWSERS_PATH'] = base
        try:
            subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], check=True, env=env)
        except Exception:
            pass

def download_requests_job(job, headers, retry, stats, lock, history_path):
    ok = False
    for i in range(retry + 1):
        try:
            with requests.get(job['url'], headers=headers, stream=True, timeout=120) as r:
                if r.status_code in [200, 206]:
                    with open(job['path'], 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1 << 20):
                            if chunk:
                                f.write(chunk)
                                with lock:
                                    stats['bytes'] += len(chunk)
                    ok = True
                    break
        except Exception:
            pass
        time.sleep(1)
    with lock:
        if ok:
            stats['completed'] += 1
        else:
            stats['failed'] += 1
    if ok:
        try:
            size = os.path.getsize(job['path']) if os.path.exists(job['path']) else 0
        except Exception:
            size = 0
        append_history(history_path, {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'url': job['url'],
            'path': job['path'],
            'name': job['name'],
            'id': job.get('id',''),
            'title': job.get('title',''),
            'author': job.get('author',''),
            'author_handle': job.get('author_handle',''),
            'publish_time': job.get('publish_time',''),
            'page_url': job.get('page_url',''),
            'mode': 'requests',
            'bytes': str(size),
            'status': 'success',
            'key': job.get('key','')
        })
    return ok

def run_downloader(url_or_id, save_dir, name_format, threads, retry, mode='requests', aria2_host='127.0.0.1', aria2_port=6800, aria2_secret='', cookie_path=os.path.join('douyin_function', 'config', 'cookie.json'), host_index=1, persist=True, debug_port=9223, login_wait_ms=60000, export_only=False, scroll_idle_max=10, scroll_interval_ms=2000, archive_by_author_id=False, archive_by_handle=False):
    os.makedirs(save_dir, exist_ok=True)
    cookie_header, cookies = parse_cookie_file(cookie_path)
    ensure_project_chromium()
    with sync_playwright() as p:
        user_data_dir = os.path.join('douyin_function', 'cache', 'playwright_profile')
        os.makedirs(user_data_dir, exist_ok=True)
        args_list = []
        if debug_port and int(debug_port) > 0:
            args_list.append(f"--remote-debugging-port={int(debug_port)}")
        if persist:
            context = p.chromium.launch_persistent_context(user_data_dir, headless=False, user_agent=UA, args=args_list or None)
        else:
            browser = p.chromium.launch(headless=False, args=args_list or None)
            context = browser.new_context(user_agent=UA, extra_http_headers={'Cookie': cookie_header} if cookie_header else None)
        if cookies:
            try:
                context.add_cookies(cookies)
            except Exception:
                pass
        page = context.new_page()
        items = collect_items(page, host_index=host_index)
        if url_or_id.startswith('http'):
            url = url_or_id
        else:
            url = f'https://www.douyin.com/user/{url_or_id}'
        page.goto(url, wait_until='domcontentloaded')
        if login_wait_ms and int(login_wait_ms) > 0:
            page.wait_for_timeout(int(login_wait_ms))
        autoscroll(page, items, max_idle=int(scroll_idle_max), interval_ms=int(scroll_interval_ms))
        time.sleep(3)
        dom_handle = extract_author_handle_from_dom(page)
        if dom_handle:
            for it in items:
                if not it.get('author_handle'):
                    it['author_handle'] = dom_handle
        if archive_by_author_id:
            aid = extract_author_id(items, url)
            if aid:
                save_dir = os.path.join(save_dir, aid)
                os.makedirs(save_dir, exist_ok=True)
        if archive_by_handle:
            handle = dom_handle
            if not handle and url_or_id and not url_or_id.startswith('http'):
                handle = url_or_id
            if handle:
                save_dir = os.path.join(save_dir, handle)
                os.makedirs(save_dir, exist_ok=True)
        cookie_used = cookie_header
        headers = {
            'User-Agent': UA,
            'Range': 'bytes=0-',
            'Referer': 'https://www.douyin.com/',
        }
        if cookie_used:
            headers['Cookie'] = cookie_used
        jobs = build_jobs(items, save_dir, name_format)
        history_path = os.path.join('douyin_function', 'config', 'histroy.csv')
        history_map_key, history_map_url = read_history_map(history_path)
        new_jobs = []
        skipped = 0
        for j in jobs:
            rec_path = history_map_key.get(j.get('key')) or history_map_url.get(j['url'])
            if not rec_path and j.get('type') == 'video':
                rec_path = find_existing_by_id(save_dir, j.get('id'))
            path_exists = os.path.exists(j['path'])
            if (rec_path and os.path.exists(rec_path)) or path_exists:
                skipped += 1
                append_history(history_path, {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'url': j.get('url',''),
                    'path': rec_path if rec_path and os.path.exists(rec_path) else (j['path'] if path_exists else ''),
                    'name': j.get('name',''),
                    'id': j.get('id',''),
                    'title': j.get('title',''),
                    'author': j.get('author',''),
                    'page_url': j.get('page_url',''),
                    'mode': mode,
                    'bytes': str(os.path.getsize(rec_path) if rec_path and os.path.exists(rec_path) else (os.path.getsize(j['path']) if path_exists else 0)),
                    'status': 'skipped',
                    'key': j.get('key','')
                })
                continue
            new_jobs.append(j)
        jobs = new_jobs
        if skipped:
            print(f"跳过已下载且文件存在的 {skipped} 个任务")
        if export_only:
            export_path = os.path.join('douyin_function', 'config', 'export_urls.txt')
            os.makedirs(os.path.dirname(export_path), exist_ok=True)
            with open(export_path, 'w', encoding='utf-8') as f:
                for j in jobs:
                    f.write(f"{j['url']}\t{j['path']}\t{j['name']}\t{j.get('id','')}\t{j.get('author','')}\t{j.get('title','')}\n")
            return jobs
        print(f"发现{len(jobs)}个可下载资源")
        for i, j in enumerate(jobs, 1):
            print(f"[{i}] {j['url']} -> {j['path']}")
        stats = {'completed': 0, 'failed': 0, 'bytes': 0}
        lock = threading.Lock()
        stop_event = threading.Event()
        def monitor():
            total = len(jobs)
            last_bytes = 0
            last_t = time.time()
            while not stop_event.is_set():
                now = time.time()
                delta_b = max(0, stats['bytes'] - last_bytes)
                delta_t = max(1e-6, now - last_t)
                speed = delta_b / delta_t
                print(f"进度: 已完成 {stats['completed']}/{total}, 跳过 {skipped}, 失败 {stats['failed']}, 已下载 {human_bytes(stats['bytes'])} 速度 {human_bytes(speed)}/s")
                last_bytes = stats['bytes']
                last_t = now
                time.sleep(1)
        mon = threading.Thread(target=monitor, daemon=True)
        mon.start()
        results = []
        if mode == 'aria2c':
            gid_to_job = {}
            for j in jobs:
                gid = download_aria2(j['url'], j['name'], save_dir, headers, host=aria2_host, port=aria2_port, secret=aria2_secret)
                if not gid:
                    ok = download_requests_job(j, headers, retry, stats, lock, history_path)
                    results.append(ok)
                else:
                    gid_to_job[gid] = j
            gid_bytes = {gid: 0 for gid in gid_to_job.keys()}
            alive = set(gid_to_job.keys())
            rpc = f'http://{aria2_host}:{aria2_port}/jsonrpc'
            def tell_status(gid):
                params = [[gid]]
                if aria2_secret:
                    params.insert(0, f'token:{aria2_secret}')
                payload = {'jsonrpc': '2.0', 'id': gid, 'method': 'aria2.tellStatus', 'params': params}
                try:
                    r = requests.post(rpc, json=payload, timeout=5)
                    if r.status_code == 200:
                        return r.json().get('result')
                except Exception:
                    return None
                return None
            while alive:
                time.sleep(1)
                for gid in list(alive):
                    st = tell_status(gid)
                    if not st:
                        continue
                    try:
                        cl = int(st.get('completedLength', '0'))
                        with lock:
                            delta = max(0, cl - gid_bytes.get(gid, 0))
                            stats['bytes'] += delta
                            gid_bytes[gid] = cl
                        status = st.get('status')
                        if status in ['complete', 'error', 'removed']:
                            alive.discard(gid)
                            with lock:
                                if status == 'complete':
                                    stats['completed'] += 1
                                    results.append(True)
                                    j = gid_to_job.get(gid, {})
                                    size = cl
                                    append_history(history_path, {
                                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'url': j.get('url',''),
                                        'path': j.get('path',''),
                                        'name': j.get('name',''),
                                        'id': j.get('id',''),
                                        'title': j.get('title',''),
                                        'author': j.get('author',''),
                                        'author_handle': j.get('author_handle',''),
                                        'publish_time': j.get('publish_time',''),
                                        'page_url': j.get('page_url',''),
                                        'mode': 'aria2c',
                                        'bytes': str(size),
                                        'status': 'success',
                                        'key': j.get('key','')
                                    })
                                else:
                                    stats['failed'] += 1
                                    results.append(False)
                    except Exception:
                        pass
        else:
            with ThreadPoolExecutor(max_workers=max(1, int(threads))) as ex:
                futs = {ex.submit(download_requests_job, j, headers, retry, stats, lock, history_path): j for j in jobs}
                for f in as_completed(futs):
                    try:
                        results.append(bool(f.result()))
                    except Exception:
                        results.append(False)
        stop_event.set()
        try:
            mon.join(timeout=2)
        except Exception:
            pass
        context.close()
        try:
            browser.close()
        except Exception:
            pass
        return results

def main():
    import argparse
    parser = argparse.ArgumentParser()
    # 参数说明：
    # --url_or_id: 抖音主页链接或作者唯一ID/抖音号；
    #              链接示例 https://www.douyin.com/user/<sec_uid>；
    #              若输入抖音号（如 xcl0624_），会用于归档与命名。
    # --save_dir: 保存根目录；
    #              若开启归档（archive_by_author_id/handle），在其下创建对应子目录。
    # --name_format: 文件命名模板；支持变量 {发布者} {标题} {id} {i} {抖音号} {时间}；
    #                变量含义：
    #                {发布者}=作者昵称；{标题}=作品标题；{id}=作品ID；
    #                {i}=当前会话顺序编号；{抖音号}=作者抖音号；
    #                {时间}=发布时间（北京时间，YYYY_MM_DD_HH_mm_ss）。
    # --threads: 并发下载线程数（requests 模式）；
    #            数值越大同时下载数越多，受网络和磁盘影响。
    # --retry: 单资源下载失败重试次数（requests 模式）；
    #          每次失败后重试，直至次数用尽。
    # --mode: 下载方式；requests 为直接下载；aria2c 通过 RPC 添加任务并轮询状态。
    # --aria2_host/port/secret: aria2c RPC 地址与密钥；
    #                           默认为 127.0.0.1:6800，无密钥。
    # --persist: 是否使用持久化浏览器上下文（1/0）；
    #            开启后保留登录态，避免二次登录。
    # --debug_port: 浏览器远程调试端口；用于复用/排查。
    # --login_wait_ms: 打开页面后的登录等待时间（毫秒）；
    #                  首次登录建议设置为正值以人工登录。
    # --export_only: 仅导出直链与保存路径，不下载（1/0）；
    #                导出路径 douyin_function/config/export_urls.txt。
    # --scroll_idle_max: 滚动采集的最大空闲轮数（默认10）；
    #                    资源数不再增长时累计空闲计数，达到上限结束采集。
    # --scroll_interval_ms: 每次滚动的间隔毫秒（默认2000）；
    #                       数值越小滚动越频繁，可能更快采集。
    # --archive_by_author_id: 是否按作者唯一ID归档到子目录（1/0）；
    #                         使用 sec_uid/输入 ID 作为子目录名。
    # --archive_by_handle: 是否按作者抖音号归档到子目录（1/0）；
    #                      优先从页面 DOM 提取“抖音号：”文本，其次响应。
    parser.add_argument('--url_or_id', default='https://www.douyin.com/user/MS4wLjABAAAALK15ylKOfoJpXG8Z61u5nxxDkqS5eznbA_8wWZgPPfU?from_tab_name=main&relation=1&vid=7575851370537245625', help='抖音主页链接或作者唯一ID/抖音号')
    parser.add_argument('--save_dir', default=os.path.join(os.getcwd(), 'downloads/douyin_test'), help='保存根目录')
    # name_format 示例与可用变量
    # 可用变量: {发布者} {标题} {id} {i} {抖音号} {时间}
    # 说明:
    # - {发布者}: 作者昵称
    # - {标题}: 作品标题
    # - {id}: 作品ID
    # - {i}: 当前会话内的顺序编号(从1递增)
    # 特别说明: 文件名会进行安全替换，特殊字符会被替换为全角或安全字符
    # 示例（以作者“笨蛋小熊”、标题“#浅跳一下#甜妹”、ID“7536958092299259193”为例）：
    # 1) 【{发布者}】{标题}({id})
    #    输出: 【笨蛋小熊】#浅跳一下#甜妹（7536958092299259193）
    # 2) {发布者}-{id}
    #    输出: 笨蛋小熊-7536958092299259193
    # 3) {i}_{标题}
    #    输出: 1_#浅跳一下#甜妹
    # 4) {发布者}_{标题}_{id}
    #    输出: 笨蛋小熊_#浅跳一下#甜妹_7536958092299259193
    # 5) {标题}（{发布者}）
    #    输出: #浅跳一下#甜妹（笨蛋小熊）
    parser.add_argument('--name_format', default='【{发布者}/{抖音号}】{时间}_{i}_{标题}({id})', help='文件命名模板，支持 {发布者} {标题} {id} {i} {抖音号} {时间}')
    parser.add_argument('--threads', type=int, default=4, help='并发下载线程数')
    parser.add_argument('--retry', type=int, default=3, help='单资源失败重试次数')
    parser.add_argument('--mode', choices=['requests', 'aria2c'], default='requests', help='下载方式')
    parser.add_argument('--aria2_host', default='127.0.0.1', help='aria2c RPC 主机')
    parser.add_argument('--aria2_port', type=int, default=6800, help='aria2c RPC 端口')
    parser.add_argument('--aria2_secret', default='', help='aria2c RPC 密钥')
    parser.add_argument('--persist', type=int, default=1, help='是否使用持久化浏览器上下文')
    parser.add_argument('--debug_port', type=int, default=9223, help='浏览器远程调试端口')
    parser.add_argument('--login_wait_ms', type=int, default=5000, help='登录等待时间（毫秒）')
    parser.add_argument('--export_only', type=int, default=0, help='仅导出直链不下载')
    parser.add_argument('--scroll_idle_max', type=int, default=10, help='滚动采集最大空闲轮数')
    parser.add_argument('--scroll_interval_ms', type=int, default=2000, help='滚动间隔毫秒')
    parser.add_argument('--archive_by_author_id', type=int, default=0, help='按作者唯一ID归档到子目录')
    parser.add_argument('--archive_by_handle', type=int, default=0, help='按作者抖音号归档到子目录')
    args = parser.parse_args()
    run_downloader(args.url_or_id, args.save_dir, args.name_format, args.threads, args.retry, mode=args.mode, aria2_host=args.aria2_host, aria2_port=args.aria2_port, aria2_secret=args.aria2_secret, persist=bool(args.persist), debug_port=args.debug_port, login_wait_ms=args.login_wait_ms, export_only=bool(args.export_only), scroll_idle_max=args.scroll_idle_max, scroll_interval_ms=args.scroll_interval_ms, archive_by_author_id=bool(args.archive_by_author_id), archive_by_handle=bool(args.archive_by_handle))

if __name__ == '__main__':
    main()

