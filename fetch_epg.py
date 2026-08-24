# -*- coding: utf-8 -*-
"""抓取合并公共 EPG 源，输出 epg.xml.gz"""
import concurrent.futures
import gzip
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from io import BytesIO

# 从 aggregate 导入映射表
sys.path.insert(0, os.path.dirname(__file__))
from aggregate import EPG_ID_MAP

EPG_SOURCES = [
    "https://epg.51zmt.top/api/epg.xml",
    "https://epg.pw/epg.xml",
    "https://epg.112114.xyz/epg.xml",
    "https://epg.51zmt.top/epg.xml",
    "https://epg.pw/epg.xml.gz",
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
TIMEOUT = 60
OUTPUT = "epg.xml.gz"


def normalize_name(name):
    """将 EPG display-name 映射为标准频道名"""
    if not name:
        return None
    name = name.strip()
    # 直接命中映射表
    if name in EPG_ID_MAP:
        return EPG_ID_MAP[name]
    # 反向查找：值匹配
    for k, v in EPG_ID_MAP.items():
        if name == v:
            return v
    # 模糊匹配：去除常见后缀
    for k, v in EPG_ID_MAP.items():
        if name.startswith(k) or k.startswith(name):
            return v
    return None


def fetch(url):
    last_err = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = r.read()
                if url.endswith(".gz") or data[:2] == b"\x1f\x8b":
                    data = gzip.decompress(data)
                return data
        except Exception as e:
            last_err = e
            if attempt == 0:
                import time
                time.sleep(2)
    raise last_err


def parse_epg(xml_bytes):
    """解析 EPG XML，返回 {标准名: (标准名, xml_element)}"""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return {}

    channels = {}
    for ch in root.findall(".//channel"):
        cid = ch.get("id")
        if not cid:
            continue
        dn = ch.find("display-name")
        raw_name = dn.text.strip() if dn is not None and dn.text else cid
        std_name = normalize_name(raw_name)
        if std_name:
            channels[std_name] = (std_name, ch)
    return channels


def merge_sources():
    all_channels = {}  # std_name -> (std_name, xml_element, source_priority)
    priority = {u: i for i, u in enumerate(EPG_SOURCES)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(fetch, u): u for u in EPG_SOURCES}
        for fut in concurrent.futures.as_completed(futures):
            url = futures[fut]
            try:
                data = fut.result()
                chs = parse_epg(data)
                print(f"  {url}: {len(chs)} channels")
                for std_name, (name, elem) in chs.items():
                    if std_name not in all_channels or priority[url] < all_channels[std_name][2]:
                        all_channels[std_name] = (std_name, elem, priority[url])
            except Exception as e:
                print(f"  {url}: FAILED {type(e).__name__}: {e}")

    print(f"Merged unique channels: {len(all_channels)}")
    return all_channels


def write_epg(channels):
    # 构建新的 XML 树
    tv = ET.Element("tv")
    tv.set("generator-info-name", "shifeiquan2-epg-merger")
    tv.set("generator-info-url", "https://github.com/shifeiquan520/shifeiquan2")

    for std_name, (name, elem, _) in sorted(channels.items()):
        ch = ET.SubElement(tv, "channel", id=std_name)
        dn = ET.SubElement(ch, "display-name")
        dn.text = std_name
        for attr in ("icon",):
            if elem.get(attr):
                ch.set(attr, elem.get(attr))

    xml_bytes = ET.tostring(tv, encoding="utf-8", xml_declaration=True)
    with gzip.open(OUTPUT, "wb", compresslevel=6) as f:
        f.write(xml_bytes)
    compressed_size = len(gzip.compress(xml_bytes, compresslevel=6))
    print(f"Written {OUTPUT} ({len(xml_bytes)} bytes -> {compressed_size} bytes compressed)")


def main():
    print("Fetching EPG sources...")
    channels = merge_sources()
    if not channels:
        print("ERROR: No channels fetched", file=sys.stderr)
        sys.exit(1)
    write_epg(channels)
    print("Done")


if __name__ == "__main__":
    main()