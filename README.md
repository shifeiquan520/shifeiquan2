# 酷9 聚合直播源

自动抓取多个公开直播源 -> 合并去重 -> 按频道分组过滤 -> **严格死链剔除** -> 输出供酷9/TVBox/DIYP 订阅。

**过滤规则**: 只保留三组频道, 其余全部剔除
- **央视频道**: 以 `CCTV` 开头, 统一为 `CCTV-X 名称` 格式 (如 `CCTV-1 综合`)
- **卫视频道**: 名称含"卫视" 或 "凤凰资讯"
- **福建频道**: 含 福建/厦门/海峡、以"东南卫视"开头、CETV/中国教育

**线路排序(严格模式)**: 每个频道内 已验证可播的 IPv4 线路排最前 -> IPv6 线路保留在后, 确保打开即播。

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
| `ku9_raw.txt` | TXT | Actions 每日自动生成的未剔死链参考文件 |
| `tv_raw.m3u` | M3U | Actions 每日自动生成的参考文件 |

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
python aggregate.py --strict   # 严格验证死链(本地推荐), 生成 ku9.txt
python aggregate.py --raw      # Actions 每日用, 只生成参考文件 ku9_raw.txt
python aggregate.py --no-check # 跳过死链剔除
```

## 死链剔除策略

- **严格模式** (`--strict`, 本地生成主订阅): 逐条 URL 请求并确认返回 `#EXTM3U`; 403/404/超时/DNS失败/非m3u8 一律删除; 只保留有存活线路的频道; **IPv4 线路排最前, IPv6 保留在后**。
- **raw 模式** (`--raw`, Actions 每日运行): 只抓取+去重+分组, 不探测死链, 输出 `ku9_raw.txt` 供参考, **不覆盖**本地严格验证的 `ku9.txt`。

> 注: GitHub Actions 跑在海外服务器, 对国内源探测会误判 (403/超时), 因此严格验证在本地网络执行后推送。

## 免责声明

仅供个人学习测试使用, 所有直播源均来自公开互联网, 请遵守当地法律法规。
