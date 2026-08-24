# -*- coding: utf-8 -*-
"""下载远程 EPG，按映射表重写 channel id，输出 epg.xml.gz"""
import gzip
import sys
import urllib.request
import xml.etree.ElementTree as ET
import os

sys.path.insert(0, os.path.dirname(__file__))
from aggregate import EPG_ID_MAP

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
URL = "https://cdn.jsdelivr.net/gh/shifeiquan520/shifeiquan2@main/epg.xml.gz"
OUTPUT = "epg.xml.gz"
TIMEOUT = 60


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
    # 模糊匹配
    for k, v in EPG_ID_MAP.items():
        if name.startswith(k) or k.startswith(name):
            return v
    return None


def main():
    print("Downloading remote EPG...")
    req = urllib.request.Request(
        "https://cdn.jsdelivr.net/gh/shifeiquan520/shifeiquan2@main/epg.xml.gz",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
    except Exception as e:
        print(f"Download failed: {e}")
        sys.exit(1)

    # 解压
    try:
        xml_bytes = gzip.decompress(data)
    except:
        xml_bytes = data

    print(f"Downloaded {len(xml_bytes)} bytes")
    root = ET.fromstring(xml_bytes)

    # 重写 channel id
    channels_fixed = 0
    for ch in root.findall(".//channel"):
        dn = ch.find("display-name")
        raw_name = dn.text.strip() if dn is not None and dn.text else ""
        
        std_name = None
        if raw_name in EPG_ID_MAP:
            std_name = EPG_ID_MAP[raw_name]
        else:
            for k, v in EPG_ID_MAP.items():
                if raw_name == v or raw_name.startswith(k) or k.startswith(raw_name):
                    std_name = v
                    break
        
        if std_name:
            ch.set("id", std_name)
            dn.text = std_name
            channels_fixed += 1

    print(f"Fixed {channels_fixed} channels")

    # 写入并压缩
    xml_bytes = ET.tostring(root.getroottree().getroot() if hasattr(root, 'getroottree') else ET.ElementTree(root).getroot(), encoding="utf-8", xml_declaration=True)
    
    with gzip.open("epg.xml.gz", "wb", compresslevel=6) as f:
        f.write(xml_bytes)
    
    print(f"Written epg.xml.gz")
    
    # 验证
    with gzip.open("epg.xml.gz", "rb") as f:
        vdata = f.read()
    vroot = ET.fromstring(vdata)
    chs = vroot.findall("channel")
    cctv = [c for c in chs if 'CCTV' in c.get('id', '')]
    print(f"验证: 总频道 {len(vroot.findall('channel'))}, CCTV相关 {len(cctv)}")
    for c in [c for c in vroot.findall("channel") if 'CCTV' in c.get('id','')][:10]:
        print(f"  {c.get('id')} -> {c.find('display-name').text if c.find('display-name') is not None else ''}")

if __name__ == "__main__":
    main()