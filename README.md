# 酷9 聚合直播源

自动抓取多个公开直播源 -> 合并去重 -> 按频道分组过滤 -> **严格死链剔除** -> 输出供酷9/TVBox/DIYP 订阅。

**完全自动维护**: 每日 04:00 (UTC) 由 GitHub Actions 自动执行严格验证并更新, 无需任何本地操作。

**过滤规则**: 只保留两组频道, 其余全部剔除
- **央视频道**: 以 `CCTV` 开头, 统一为 `CCTV-X 名称` 格式 (如 `CCTV-1 综合`)
- **卫视频道**: 名称含"卫视" 或 "凤凰资讯" (含 东南卫视/厦门卫视/海峡卫视 等)

**线路排序**: 每个频道内 **已验证可播线路按测速降序排最前**, **无速度(line 为 time 剔除)**, **速度低于 20KB/s 的剔除**; 每频道最多 8 条; 彻底剔除 IPv6 与广播台。

## 订阅地址

酷9 使用：设置 -> 列表配置 -> 列表订阅 -> 输入地址 -> 确定 -> 勾选启用

- **raw 直链**: `https://raw.githubusercontent.com/shifeiquan520/shifeiquan2/main/ku9.txt`
- **jsDelivr 加速**(国内快, 缓存最长24h): `https://cdn.jsdelivr.net/gh/shifeiquan520/shifeiquan2@main/ku9.txt`
- **M3U 格式**(通用播放器/APTV/DIYP): `https://raw.githubusercontent.com/shifeiquan520/shifeiquan2/main/tv.m3u`

## 输出文件

| 文件 | 格式 | 用途 |
|---|---|---|
| `ku9.txt` | TXT (频道,url1#url2) | 酷9 专用, 同名频道多线路自动换线, 分组: 央视频道→卫视频道 |
| `tv.m3u` | M3U | 通用格式 |

## 源清单

编辑 `sources.json` 可增删源, `enabled: false` 即可停用。

| 源 | 说明 |
|---|---|
| hepingcaizi/iptv `itvlist.txt` | 央视酒店源, 1013 条线路, UTF-8 |
| hepingcaizi/iptv `weishi.txt` | 卫视酒店源, 301 条线路, UTF-8 |
| best-fan/iptv-sources | 央视/卫视, 纯国内 IPv4, 每日自动更新 |
| hujingguang/ChinaIPTV | 港澳台 |
| vamoschuck/TV | 茶客源 |
| myernestlu/zby | 经典 TXT 源 |
| jincg99/tvbox | 酷9 源 |
| zilong7728/Collect-IPTV | 每6小时更新的多源聚合 |
| bestfan_cctv | 央视源 |
| bestfan_province | 卫视源 |
| ChinaIPTV | 自动更新源 |