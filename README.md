# 酷9 聚合直播源

自动抓取多个公开直播源 -> 合并去重 -> 按频道分组过滤 -> 宽松死链剔除 -> 输出供酷9/TVBox/DIYP 订阅。

**过滤规则**: 只保留三组频道, 其余全部剔除
- **央视频道** (23): 以 `CCTV` 开头, 统一为 `CCTV-X 名称` 格式 (如 `CCTV-1 综合`)
- **卫视频道** (80): 名称含"卫视" 或 "凤凰资讯"
- **福建频道** (26): 含 福建/厦门/海峡、以"东南卫视"开头、CETV/中国教育

每日 04:00 (UTC) 由 GitHub Actions 自动更新。

## 订阅地址

酷9 使用：设置 -> 列表配置 -> 列表订阅 -> 输入地址 -> 确定 -> 勾选启用

- **raw 直链**: `https://raw.githubusercontent.com/shifeiquan520/shifeiquan2/main/ku9.txt`
- **jsDelivr 加速**(国内快, 缓存最长24h): `https://cdn.jsdelivr.net/gh/shifeiquan520/shifeiquan2@main/ku9.txt`
- **M3U 格式**(通用播放器/APTV/DIYP): `https://raw.githubusercontent.com/shifeiquan520/shifeiquan2/main/tv.m3u`

## 输出文件

| 文件 | 格式 | 用途 |
|---|---|---|
| `ku9.txt` | TXT (频道,url1#url2) | 酷9 专用, 同名频道多线路自动换线, 分组: 央视频道→卫视频道→福建频道 |
| `tv.m3u` | M3U | 通用格式 |

## 源清单

编辑 `sources.json` 可增删源, `enabled: false` 即可停用。

| 源 | 说明 |
|---|---|
| fanmingming/live | 范明明, IPv6 央视卫视 |
| zbefine/iptv | 综合大源 |
| Kimentanm/aptv | APTV 源 |
| YanG-1989/m3u | YanG 聚合 |
| BigBigGrandG/IPTV-URL | 大聚合 |
| hujingguang/ChinaIPTV | 港澳台 |
| Guovin/iptv-api | 自动更新 |
| vamoschuck/TV | 茶客源 |
| myernestlu/zby | 经典 TXT 源 |

## 本地运行

```bash
python aggregate.py            # 含宽松死链剔除
python aggregate.py --no-check # 跳过死链剔除, 更快
```

## 死链剔除策略

宽松模式, 避免海外 Actions 服务器误判国内源:

- **删除**: HTTP 404/410、连接被拒绝
- **保留**: 403(地域封锁)、超时、DNS 解析失败等一律保留

## 免责声明

仅供个人学习测试使用, 所有直播源均来自公开互联网, 请遵守当地法律法规。
