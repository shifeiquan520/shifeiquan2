# -*- coding: utf-8 -*-
"""酷9 直播源聚合脚本
抓取 sources.json 中的直播源 -> 解析 TXT/M3U -> 合并去重 -> 宽松死链剔除 -> 输出 ku9.txt + tv.m3u
"""
import concurrent.futures
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "sources.json")
OUTPUT_TXT = os.path.join(SCRIPT_DIR, "ku9.txt")
OUTPUT_M3U = os.path.join(SCRIPT_DIR, "tv.m3u")
OUTPUT_RAW_TXT = os.path.join(SCRIPT_DIR, "ku9_raw.txt")
OUTPUT_RAW_M3U = os.path.join(SCRIPT_DIR, "tv_raw.m3u")
LOG_FILE = os.path.join(SCRIPT_DIR, "log", "last_run.json")

FETCH_TIMEOUT = 30
CHECK_TIMEOUT = 4
STRICT_TIMEOUT = 6
SPEED_TIMEOUT = 8
CHECK_CONCURRENCY = 30
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def fetch(url, encoding="auto"):
    last_err = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
                data = r.read()
            break
        except Exception as e:
            last_err = e
            if attempt == 0:
                time.sleep(2)
    else:
        raise last_err
    if encoding in ("gbk", "gb2312"):
        return data.decode("gbk", errors="ignore")
    if encoding in ("utf-8", "utf8"):
        return data.decode("utf-8", errors="ignore")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("gbk", errors="ignore")


def parse_txt(text):
    """解析酷9 TXT 格式:  '分组,#genre#' 和 '频道名,url1#url2'"""
    channels = []
    current_group = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.lower().endswith("#genre#"):
            current_group = line[:-7].strip()
            continue
        if "," in line:
            name, _, urls = line.partition(",")
            name = name.strip()
            urls = urls.strip()
            if not name or not urls:
                continue
            url_list = [u.strip() for u in re.split(r"[#]+", urls) if u.strip()]
            if url_list:
                channels.append({"name": name, "group": current_group, "urls": url_list})
    return channels


def parse_m3u(text):
    """解析 M3U 格式"""
    channels = []
    current_group = ""
    pending = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTGRP:"):
            current_group = line[8:].strip()
            continue
        if line.startswith("#EXTINF"):
            m = re.search(r'tvg-name="([^"]*)"', line)
            name = m.group(1) if m else ""
            if not name:
                m = re.search(r'^#EXTINF[^,]*,(.+)$', line)
                name = m.group(1).strip() if m else ""
            pending = name
            continue
        if line.startswith("#"):
            continue
        url = line
        if not pending:
            pending = ""
        if url.startswith("http://") or url.startswith("https://"):
            channels.append({"name": pending, "group": current_group, "urls": [url]})
        pending = None
    return channels


def merge_dedupe(all_channels):
    """按频道名合并线路, 按 URL 去重"""
    merged = {}
    for ch in all_channels:
        name = ch["name"].strip()
        if not name:
            continue
        key = name
        if key not in merged:
            merged[key] = {"name": name, "group": ch.get("group", ""), "urls": []}
        for u in ch["urls"]:
            if u not in merged[key]["urls"]:
                merged[key]["urls"].append(u)
    return list(merged.values())


def probe(url):
    """宽松探测: 只剔除明确死亡的链接
    删除条件: HTTP 404/410 或 连接被拒绝
    保留条件: 403(地域封锁)/超时/DNS失败/其它 一律保留, 避免海外误判国内源
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-1024"}, method="GET")
        with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT) as r:
            r.status
        return True
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return False
        return True
    except urllib.error.URLError:
        return True
    except (ConnectionRefusedError, OSError) as e:
        errno_val = getattr(e, "errno", None)
        if errno_val in (111, 10061):
            return False
        return True
    except Exception:
        return True


def filter_dead(channels):
    """宽松死链剔除(可选): 逐条URL探测, 保留存活线路; 全部死亡才删频道"""
    tasks = []
    for ch in channels:
        for u in ch["urls"]:
            tasks.append((ch, u))

    dead_urls = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=CHECK_CONCURRENCY) as ex:
        futures = {ex.submit(probe, u): u for ch, u in tasks}
        for fut in concurrent.futures.as_completed(futures):
            u = futures[fut]
            try:
                ok = fut.result()
            except Exception:
                ok = True
            if not ok:
                dead_urls.add(u)

    alive = []
    for ch in channels:
        urls = [u for u in ch["urls"] if u not in dead_urls]
        if urls:
            ch["urls"] = urls
            alive.append(ch)
    return alive


def is_ipv6_url(url):
    """判断是否为 IPv6 地址形式的 URL(带方括号)"""
    m = re.search(r'://(\[[0-9a-fA-F:]+\])', url)
    return bool(m)


def speed_probe(url):
    """测速探测: 确认 m3u8 可播并测量下载速度
    返回: (验证状态, 速度KB/s)
      'ok'   -> 可播且有速度, 排最前
      'http' -> HTTP 错误码(403/404/410/5xx), 判死
      'time' -> 超时/DNS失败/连接拒绝(源可能只在特定网络可达), 保留但排末尾
    """
    status = "ok"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-4096"}, method="GET")
        with urllib.request.urlopen(req, timeout=SPEED_TIMEOUT) as r:
            if r.status not in (200, 206):
                return ("http", 0.0)
            data = r.read(8192)
            if b"#EXTM3U" not in data:
                return ("http", 0.0)
    except urllib.error.HTTPError:
        return ("http", 0.0)
    except Exception:
        return ("time", 0.0)

    # 解析 m3u8 中第一个片段地址
    try:
        base = url.rsplit("/", 1)[0] + "/"
        seg = None
        for line in data.decode("utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and (".ts" in line.lower() or "index" in line.lower()):
                seg = line
                break
        if not seg:
            return ("http", 0.0)
        if seg.startswith("http://") or seg.startswith("https://"):
            ts_url = seg
        elif seg.startswith("/"):
            m2 = re.match(r'^(https?://[^/]+)', url)
            ts_url = (m2.group(1) if m2 else "") + seg
        else:
            ts_url = base + seg
    except Exception:
        return ("http", 0.0)

    # 下载片段测速
    try:
        req2 = urllib.request.Request(ts_url, headers={"User-Agent": UA}, method="GET")
        t0 = time.time()
        with urllib.request.urlopen(req2, timeout=SPEED_TIMEOUT) as r2:
            if r2.status not in (200, 206):
                return ("http", 0.0)
            chunk = r2.read(32768)
        dt = time.time() - t0
        if dt <= 0:
            return ("time", 0.0)
        speed = len(chunk) / 1024.0 / dt
        return ("ok", speed)
    except urllib.error.HTTPError:
        return ("http", 0.0)
    except Exception:
        return ("time", 0.0)


MAX_LINES_PER_CHANNEL = 8


def filter_strict(channels):
    """保底式严格剔除:
    去除 IPv6; HTTP 错误码(403/404/410/5xx)判死删除;
    超时/DNS/连接拒绝(可能只在特定网络可达)保留为保底线路, 排末尾;
    每频道线路按: 可播(按速度降序)在前 -> 未验证保底在后; 每频道最多 MAX_LINES_PER_CHANNEL 条;
    频道至少保留 1 条保底线路(不因探测环境误删频道); 全死(HTTP错误)才删除频道
    """
    tasks = []
    for ch in channels:
        for u in ch["urls"]:
            if not is_ipv6_url(u):
                tasks.append(u)
    results = {}
    if tasks:
        with concurrent.futures.ThreadPoolExecutor(max_workers=CHECK_CONCURRENCY) as ex:
            futures = {ex.submit(speed_probe, u): u for u in tasks}
            for fut in concurrent.futures.as_completed(futures):
                u = futures[fut]
                try:
                    results[u] = fut.result()
                except Exception:
                    results[u] = ("time", 0.0)

    alive = []
    for ch in channels:
        ok, http, tmo = [], [], []
        for u in ch["urls"]:
            if is_ipv6_url(u):
                continue
            st, spd = results.get(u, ("time", 0.0))
            if st == "ok":
                ok.append((u, spd))
            elif st == "http":
                http.append(u)
            else:
                tmo.append(u)
        ok.sort(key=lambda x: x[1], reverse=True)
        ok = [u for u, _ in ok]
        http_urls = set(http)
        tmo = [u for u in tmo if u not in http_urls]
        urls = ok[:MAX_LINES_PER_CHANNEL]
        remaining = MAX_LINES_PER_CHANNEL - len(urls)
        if remaining > 0:
            urls += tmo[:remaining]
        if urls:
            ch["urls"] = urls
            alive.append(ch)
    return alive


CCTV_NAMES = {
    "CCTV1": "CCTV-1 综合",
    "CCTV2": "CCTV-2 财经",
    "CCTV3": "CCTV-3 综艺",
    "CCTV4": "CCTV-4 中文国际",
    "CCTV5": "CCTV-5 体育",
    "CCTV5+": "CCTV-5+ 体育赛事",
    "CCTV6": "CCTV-6 电影",
    "CCTV7": "CCTV-7 国防军事",
    "CCTV8": "CCTV-8 电视剧",
    "CCTV9": "CCTV-9 纪录",
    "CCTV10": "CCTV-10 科教",
    "CCTV11": "CCTV-11 戏曲",
    "CCTV12": "CCTV-12 社会与法",
    "CCTV13": "CCTV-13 新闻",
    "CCTV14": "CCTV-14 少儿",
    "CCTV15": "CCTV-15 音乐",
    "CCTV16": "CCTV-16 奥林匹克",
    "CCTV17": "CCTV-17 农业农村",
    "CCTV4K": "CCTV-4K 超高清",
    "CCTV8K": "CCTV-8K 超高清",
}
CCTV_SPECIAL = {
    "CCTV女时尚": "CCTV-女性时尚",
    "CCTV老故事": "CCTV-老故事",
    "CCTV新闻动漫": "CCTV-新闻动漫",
    "CCTV鏂扮戝姩婕": "CCTV-新科动漫",
}
GROUP_ORDER = ["央视频道", "卫视频道", "福建频道"]


def normalize_cctv(name):
    """将各种 CCTV 变体统一为 'CCTV-X 名称' 格式"""
    n = name.strip()
    m = re.match(r'^CCTV[- ]?[48]K$', n)
    if m:
        return CCTV_NAMES.get("CCTV" + m.group(0)[-2:])
    m = re.match(r'^CCTV[- ]?5\+', n)
    if m:
        return CCTV_NAMES["CCTV5+"]
    m = re.match(r'^CCTV[- ]?(\d+)', n)
    if m:
        key = "CCTV" + m.group(1)
        if key in CCTV_NAMES:
            return CCTV_NAMES[key]
    if n in CCTV_SPECIAL:
        return CCTV_SPECIAL[n]
    return n


def classify(name):
    """按优先级分到三组, 其余返回 None"""
    if "广播" in name:
        return None
    if re.match(r'^CCTV', name, re.I):
        return "央视频道"
    if ("福建" in name or "厦门" in name or "海峡" in name
            or name.startswith("东南卫视")
            or "CETV" in name.upper() or name.startswith("中国教育")):
        return "福建频道"
    if "卫视" in name or "凤凰资讯" in name:
        return "卫视频道"
    return None


def fujian_key(ch):
    """福建频道组内排序: 福建*开头最上 -> 东南卫视 -> 教育类 -> 其余"""
    name = ch["name"]
    if name.startswith("福建"):
        return (0, name)
    if name.startswith("东南卫视"):
        return (1, name)
    if "CETV" in name.upper() or name.startswith("中国教育"):
        return (2, name)
    return (3, name)


def filter_group(channels):
    """统一 CCTV 名称 -> 分类 -> 只保留三组"""
    kept = []
    for ch in channels:
        name = ch["name"]
        if re.match(r'^CCTV', name, re.I):
            name = normalize_cctv(name)
        g = classify(name)
        if not g:
            continue
        ch["name"] = name
        ch["group"] = g
        kept.append(ch)
    return kept


def to_txt(channels):
    lines = ["# 更新时间: %s" % time.strftime("%Y-%m-%d %H:%M:%S"), ""]
    by_group = {}
    for ch in channels:
        g = ch.get("group", "") or "未分组"
        by_group.setdefault(g, []).append(ch)
    for g in GROUP_ORDER:
        if g not in by_group:
            continue
        lines.append("%s,#genre#" % g)
        for ch in by_group[g]:
            lines.append("%s,%s" % (ch["name"], "#".join(ch["urls"])))
        lines.append("")
    return "\n".join(lines)


def to_m3u(channels):
    lines = ["#EXTM3U"]
    for ch in channels:
        g = ch.get("group", "")
        for u in ch["urls"]:
            if g:
                lines.append("#EXTGRP:%s" % g)
            lines.append('#EXTINF:-1 tvg-name="%s",%s' % (ch["name"], ch["name"]))
            lines.append(u)
    return "\n".join(lines)


def main():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    enabled = [s for s in cfg["sources"] if s.get("enabled", True)]
    print("启用 %d 个源" % len(enabled))

    all_channels = []
    per_source = {}
    for s in enabled:
        try:
            text = fetch(s["url"], s.get("encoding", "auto"))
            if s.get("type") == "txt":
                chs = parse_txt(text)
            else:
                chs = parse_m3u(text)
            all_channels.extend(chs)
            per_source[s["name"]] = {"status": "ok", "channels": len(chs)}
            print("  [OK] %s -> %d channels" % (s["name"], len(chs)))
        except Exception as e:
            per_source[s["name"]] = {"status": "err", "channels": 0, "error": str(e)[:120]}
            print("  [ERR] %s -> %s" % (s["name"], e))

    print("抓取完成, 原始频道 %d" % len(all_channels))
    merged = merge_dedupe(all_channels)
    print("合并去重后: %d" % len(merged))

    merged = filter_group(merged)
    merged = merge_dedupe(merged)  # CCTV 统一名称后再合并一次
    print("过滤后(仅央视/卫视/福建): %d" % len(merged))
    from collections import Counter
    gc = Counter(ch["group"] for ch in merged)
    for g in GROUP_ORDER:
        print("  %s: %d" % (g, gc.get(g, 0)))

    if "--raw" in sys.argv:
        print("== raw 模式: 只抓取+分组, 不探测死链 ==")
        fujian = [ch for ch in merged if ch["group"] == "福建频道"]
        fujian.sort(key=fujian_key)
        others = [ch for ch in merged if ch["group"] != "福建频道"]
        merged = others + fujian
        with open(OUTPUT_RAW_TXT, "w", encoding="utf-8") as f:
            f.write(to_txt(merged))
        with open(OUTPUT_RAW_M3U, "w", encoding="utf-8") as f:
            f.write(to_m3u(merged))
        print("已输出 ku9_raw.txt (%d 频道) 和 tv_raw.m3u" % len(merged))
        return

    if "--strict" in sys.argv:
        print("开始严格死链剔除(测速+保底, 超时 %ds)... " % SPEED_TIMEOUT)
        before_urls = sum(len(ch["urls"]) for ch in merged)
        merged = filter_strict(merged)
        after_urls = sum(len(ch["urls"]) for ch in merged)
        print("严格剔除: URL %d -> %d, 频道 %d 剩余" % (
            before_urls, after_urls, len(merged)))
    else:
        do_check = "--no-check" not in sys.argv
        if do_check:
            print("开始宽松死链剔除(%d 条探测, 超时 %ds)... " % (len(merged), CHECK_TIMEOUT))
            merged = filter_dead(merged)
            print("剔除后剩余: %d" % len(merged))

    # 福建频道组内排序(福建* -> 东南卫视 -> 教育 -> 其余)
    fujian = [ch for ch in merged if ch["group"] == "福建频道"]
    fujian.sort(key=fujian_key)
    others = [ch for ch in merged if ch["group"] != "福建频道"]
    merged = others + fujian

    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write(to_txt(merged))
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(to_m3u(merged))
    print("已输出 ku9.txt (%d 频道) 和 tv.m3u" % len(merged))

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source_count": len(enabled),
            "merged": len(merged),
            "per_source": per_source,
        }, f, ensure_ascii=False, indent=2)
    print("日志已写入 log/last_run.json")


if __name__ == "__main__":
    main()
