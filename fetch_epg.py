# -*- coding: utf-8 -*-
"""抓取合并公共 EPG 源，输出 epg.xml.gz"""
import concurrent.futures
import gzip
import sys
import urllib.request
import xml.etree.ElementTree as ET
from io import BytesIO

EPG_SOURCES = [
    "https://epg.pw/epg.xml",
    "https://epg.51zmt.top/api/epg.xml",
    "https://epg.112114.xyz/epg.xml",
    "https://epg.51zmt.top/epg.xml",
    "https://epg.pw/epg.xml.gz",
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
TIMEOUT = 30
OUTPUT = "epg.xml.gz"


def fetch(url):
    last_err = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = r.read()
                # 如果是 gzip 压缩，解压
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
    """解析 EPG XML，返回 {channel_id: (display_name, xml_element)}"""
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
        name = dn.text.strip() if dn is not None and dn.text else cid
        channels[cid] = (name, ch)
    return channels


def merge_sources():
    all_channels = {}  # cid -> (name, xml_element, source_priority)
    priority = {u: i for i, u in enumerate(EPG_SOURCES)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(fetch, u): u for u in EPG_SOURCES}
        for fut in concurrent.futures.as_completed(futures):
            url = futures[fut]
            try:
                data = fut.result()
                chs = parse_epg(data)
                print(f"  {url}: {len(chs)} channels")
                for cid, (name, elem) in chs.items():
                    if cid not in all_channels or priority[url] < all_channels[cid][2]:
                        all_channels[cid] = (name, elem, priority[url])
            except Exception as e:
                print(f"  {url}: FAILED {type(e).__name__}: {e}")

    print(f"Merged unique channels: {len(all_channels)}")
    return all_channels


def write_epg(channels):
    # 构建新的 XML 树
    tv = ET.Element("tv")
    tv.set("generator-info-name", "shifeiquan2-epg-merger")
    tv.set("generator-info-url", "https://github.com/shifeiquan520/shifeiquan2")

    for cid, (name, elem, _) in sorted(channels.items()):
        # 复制原 channel 元素，确保只保留 id 和 display-name
        ch = ET.SubElement(tv, "channel", id=cid)
        dn = ET.SubElement(ch, "display-name")
        dn.text = name
        # 保留原有 icon 等属性
        for attr in ("icon",):
            if elem.get(attr):
                ch.set(attr, elem.get(attr))

    # 写入并压缩
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