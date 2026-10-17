# PE-Trace · 全球股指滚动市盈率分位

查询全球主要股指的**滚动窗口 PE 分位数**与指数点位走势，用于观察各市场当前的估值溢价水平。

本页所有指标均为对**公开数据的确定性统计描述**，仅供研究参考，不构成投资建议。

---

## 快速开始

```powershell
# 1) 生成数据（首次约 5–8 分钟；之后走缓存，秒级）
& $py -m petrace.build

# 2) 起一个静态服务（数据是纯静态 JSON，无需后端）
& $py -m tools.serve                  # 默认 http://127.0.0.1:8791/

# 3) 打开 http://127.0.0.1:8791/
```

`$py` 是本机捆绑解释器：

```
C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe
```

> **不要用 `python -m http.server`。** 它完全不发 `Cache-Control`，浏览器于是按
> 「文件年龄的 10%」做**启发式缓存**，可能直接用旧的 `app.js` 而不回源——开发中曾因此
> 让一个已修好的前端缺陷看起来没生效。`tools/serve.py` 对 html/js/css 发 `no-cache`
> （保留副本但**必须**用 `If-Modified-Since` 回源，未改动时是一枚极小的 304），
> 对 `data/*.json` 发 `no-store`（根本不落盘）。本项目的数据由定时任务刷新，
> 读者刷新页面必须拿到新数字，这一条不是优化项。

### 常用参数

| 参数 | 说明 |
|---|---|
| `--refresh` | 忽略磁盘缓存，强制重取（上游限流时慎用） |
| `--offline` | 只读缓存，不联网；上游全挂时仍可出页 |
| `--only SH000300,SP500` | 只重建指定指数（调试用）。**不会**缩小数据层：其余指数沿用上一次的结果，`counts` 仍描述全量 |
| `--min-interval 0.7` | 每主机最小请求间隔（秒），上调可降低被限流概率 |
| `--max-age 6` | 缓存有效期（**小时**）。超过则重新抓取；失败时回退到旧副本并在 `freshness.stale_responses` 计数 |
| `--skip-legulegu` | 跳过乐咕乐股（该站长期 504，能省数分钟） |
| `--verbose` | 打印每条价格链的命中情况 |

---

## 部署到公网

站点是**纯静态文件**（无后端、无密钥），但数据必须**在本机重建**——蛋卷 / 中证 / 新浪 / 腾讯
这些上游从中国大陆访问才稳定可达，把构建搬到国外 CI runner 会直接拿不到数据。所以管道是：

```
本机定时重建（tools/update.py） → 只发布 web/ 目录 → 公网静态托管
```

### 当前线上地址

已部署两个入口，内容完全相同（同一份 `web/` 产物）：

| 入口 | 地址 | 大陆直连 | 说明 |
|---|---|---|---|
| **GitHub Pages** | https://baelish98-coder.github.io/PE-Trace/ | ✅ 直连可用 | **推荐日常访问**，免备案、可长期、无需代理 |
| **Vercel** | https://pe-trace.vercel.app/ | ⚠️ 需代理 | 本机被 Steam++ 按 SNI 拦截，见下 |

仓库：https://github.com/baelish98-coder/PE-Trace

**为什么 Vercel 在本机打不开（根因已定位）**：不是 Vercel 故障，也不是单纯 DNS 污染，
而是**本机有一个按 SNI 名字白名单放行的传输层拦截**。证据链：

- 同一 IP、同一端口，只换 SNI：打 `76.76.21.21:443` 时 `nextjs.org` → **200**，
  `pe-trace.vercel.app` / `example.com` / `www.baidu.com` → **000**（连 `baidu.com` 都被拒，
  说明不是「封 Vercel」而是「只放行少数名字」）；
- `nextjs.org` 本身就跑在 Vercel 上，响应头带 `Server: Vercel` + `X-Vercel-Pop: NRT12-P2`，
  证明 Vercel 服务本身可达；
- 拦截者：`Steam++.Accelerator.exe` 监听 `0.0.0.0:443` 与 `0.0.0.0:80`，
  并把 `github.com` 等 47 个域名写进 hosts 指向 `127.0.0.1`；
- **真正的开关是 Clash Verge**：`verge.yaml` 里 `enable_auto_launch: false`，即它默认**不会自启**。
  它一旦没跑，7897 端口就是死的，而系统代理（WinINET）仍指向 `127.0.0.1:7897`
  → 所有 `*.vercel.app` 只能退化到直连 → 撞上上面那层 SNI 白名单 → 000。

**修复与自愈**：Clash Verge 起来后（`Start-Process 'C:\Program Files\Clash Verge\clash-verge.exe'`，
约 2s 监听 7897），经代理访问 `pe-trace.vercel.app` 立即恢复 `200`。为了不再依赖手动启动，
`tools/autoupdate.py --ensure-proxy`（已由常驻调度器 `tools/scheduler.py` 带 `--ensure-proxy` 调用）
会在 7897 不通时自动拉起 Clash Verge。**验证方式**：

```powershell
# 代理活着时应为 200
curl.exe -s -o NUL -w "code=%{http_code}`n" --proxy http://127.0.0.1:7897 https://pe-trace.vercel.app/
# GH Pages 无需代理也应 200
curl.exe -s -o NUL -w "code=%{http_code}`n" https://baelish98-coder.github.io/PE-Trace/
```

若要让大陆访问者**免代理**直连 Vercel，唯一可靠办法是在 Vercel 项目里绑定一个未被上述
拦截/污染影响的自定义域。

> Vercel 项目的 **Deployment Protection 默认开启**（`ssoProtection.deploymentType =
> "all_except_custom_domains"`），会导致所有访客被弹 Vercel 登录墙、`curl` 拿到的是登录页
> 而不是站点。公开数据看板必须关掉：
> ```powershell
> cd web
> & vercel link --yes --project pe-trace
> & vercel project protection disable --sso     # 关闭后 ssoProtection 变为 null
> ```
> 关闭后用**不带任何 token** 的 `curl` 验证：`curl -s -x http://127.0.0.1:7897 -o NUL -w "%{http_code}" https://pe-trace.vercel.app/` 应返回 `200`。

### 部署方式

```powershell
# A) GitHub Pages（push 即自动发布，见 .github/workflows/deploy-pages.yml）
git add -A; git commit -m "..."; git push origin main
#    仅当改动命中 web/** 或工作流文件时触发，避免纯文档提交白跑一次

# B) Vercel（手动部署；web/ 目录已 vercel link 到项目 pe-trace）
cd web
& vercel deploy --prod --yes
```

> 两个平台的触发方式刻意不同：**GitHub Pages 走 push 触发**，因为数据是在本机重建后
> 提交的，Actions 只负责搬运 `web/`；**Vercel 走手动 CLI**，因为 `vercel git connect`
> 需要 GitHub Login Connection（本账号尚未建立，报 `You need to add a Login Connection
> to your GitHub account first. (400)`）。
>
> 若只想发布数据更新，用 `tools/autoupdate.py`（下面「自动周期性更新」一节）在重建成功后
> 自动提交并推送，Pages 会自动跟随。

### 选哪家：中国大陆直连实测

下面的数字是 2026-10-10 在本机（上海移动出口，**无代理**）用 `curl` 实测的。关键指标是
**首屏关键路径的传输吞吐**，不是首页延迟——本页首屏要拉 1.03 MB 的 ECharts 加最多
~310 KB 的单指数 JSON，小文件快而大文件慢的平台在这里会露馅。

首屏关键路径（index+app+css+echarts+manifest+summary+一个指数 JSON）共 **1.50 MB，
压缩后 459 KB**（ECharts 压到 32%）。各平台都启用了压缩，所以按压缩后比较：

| 托管 | 同体积资源 5 次实测 | 459 KB 关键路径 | 结论 |
|---|---|---|---|
| **腾讯 EdgeOne Makers** | 336 KB 用 **0.39–0.48 s**（@brotli，**700–867 KB/s**） | **≈ 0.6 s** | ✅ 最快，但需备案+自定义域才能长期用 |
| **GitHub Pages**（185.199.x） | 491 KB 用 **6.9–15.0 s**（@gzip，**33–71 KB/s**） | **≈ 6–15 s** | ✅ **已上线**，免备案、可长期 |
| Vercel（`*.vercel.app`） | 20 s 超时（000），**仅本机不可达** | 数秒（他网） | ⚠️ **已上线**，本机需代理才能打开 |
| Netlify（`*.netlify.app`） | TTFB 1.2–2.3 s | 数秒 | 可用，但 2026 改 credit 制后每日部署会击穿额度 |
| Cloudflare Pages（`*.pages.dev`） | 4 个测试站中 **3 个**返回 HTTP 522 | — | ❌ 免费档用不到大陆节点 |
| Gitee Pages | 帮助中心已无 Pages 词条，`gitee.io` 超时 | — | ❌ 已停服 |

EdgeOne 实测由 **211.136.106.223**（AS24400 上海移动）这个边缘节点服务——即节点落在
访客所在 ISP 网内，这也是它能跑到近 1 MB/s 的原因。

> **测量口径提醒（我一开始就搞错过）**：GitHub Pages 虽然慢，但它**会**发 gzip，
> 所以按"原始 1.5 MB ÷ 实测速率"会算出 60 秒，实际只要 **6–15 秒**。比较吞吐必须
> 两端都开 `--compressed`，并用压缩后的字节数。另外它的中小文件延迟其实很好
> （`*.github.io` 首页 20/20 全 200、均值 0.47 s）——**"慢"只体现在大文件吞吐上**，
> 这也是为什么单看首页延迟会得出相反结论。

EdgeOne 是腾讯自家的免费档，官方明确定位为「首个**含中国大陆访问**的免费 CDN」，
免费额度不限流量、不限请求数，因此作为默认方案。

**EdgeOne 免费档的三条硬约束**（官方文档逐字确认，免费默认域不能当长期入口）：

1. **免费默认域在大陆只有 3 小时有效**：「通过**项目域名**及**部署域名**访问 Makers 站点…
   中国大陆网络环境须使用系统生成的预览链接进行访问，该链接有效期为 3 小时，超时后将返回 401 错误。」
2. **证书不会自动分配**：「Makers **不会自动**为您的域名分配 HTTPS 证书」——需在控制台
   手动申请一次免费证书（TrustAsia / Let's Encrypt）。
3. **要拿到大陆加速节点必须 ICP 备案**：加速区选「中国大陆可用区」或「全球可用区（含中国大陆）」时
   「添加的域名需先在工信部完成备案」。**全球可用区（不含中国大陆）无需备案**，但也就拿不到大陆节点。

→ 因此**当前这个匿名 URL 只是演示**：它 3 小时内有效、且每次部署都会新建项目。
要长期稳定，必须绑定自定义域名（备案与否决定能否用大陆节点）。

> 测速方法论坑：`*.github.io` **不一定**在 GitHub 上。`chinese-poetry.github.io` 实际解析到
> Cloudflare（104.21.x），`d3js.org` / `getbootstrap.com` 也在 Cloudflare。判断"GitHub Pages
> 速度"必须核对 `%{remote_ip}` 属于 `185.199.108-111.153`，否则量的是 Cloudflare。
> 另外 PowerShell 的 `Invoke-WebRequest` 会把 301 报成 `000`（看起来像失败），判定可达性要用 `curl.exe`。

### 备选：GitHub Pages（免费、无备案要求，但大文件慢）

如果不想注册腾讯云账号，GitHub Pages 是唯一"无需备案且大陆可达"的免费选项：
public 仓库的 Actions 完全免费，用官方自定义工作流（`actions/configure-pages@v5` →
`actions/upload-pages-artifact@v4` → `actions/deploy-pages@v4`）发布可绕开
「10 builds/hour」软上限；自定义域名 + HTTPS 自动。代价就是上表那 6–15 秒首屏。

> **本机特有的坑**：这台机器的 `hosts` 把 `github.com` / `api.github.com` /
> `github.io` / `raw.githubusercontent.com` 等全部指向 `127.0.0.1`（某加速工具所致），
> 实测 `git ls-remote https://github.com/...` 直接报
> `SSL certificate ... unable to get local issuer certificate`，用真实 IP `--resolve`
> 也超时。**要推送到 GitHub 必须先清掉这些 hosts 条目**。注意这只影响本机推送，
> 不影响其他大陆访客访问 `*.github.io`（实测 20/20 全 200、均值 0.47 s）。

### 用法

```powershell
# 首次需要安装 CLI
npm install -g edgeone

# A) 免账号快照：立刻拿到一个可访问 URL，但会过期，需 claim 才能保留
& $py -m tools.deploy --anonymous

# B) 正式：在 EdgeOne Makers 控制台生成 API Token，设为环境变量后发布到固定域名
setx EDGEONE_API_TOKEN "你的token"     # 设完要重开终端
& $py -m tools.deploy                  # 自动读取该变量，发布到项目 pe-trace
```

`--anonymous` 模式**每次都会新建一个项目**，URL 带 `?eo_token=…&eo_time=…` 且约 3 小时后
随项目一起被删除。想保留就执行它打印的 `edgeone makers claim --sid <token>`，或在浏览器打开
`claimUrl` 登录腾讯云认领。要长期稳定，用 B 方案的 API Token + **绑定自定义域名**——
免费默认域在大陆只有 3 小时有效期（见上）。

> `claim` 之后项目会留在你的腾讯云账号下，但**免费默认域仍受 3 小时预览限制**；
> 想给访客一个长期可用的地址，必须绑自定义域名。域名已备案 → 可选用大陆加速区
> （实测节点在访客本省移动网内）；未备案 → 只能选「全球可用区（不含中国大陆）」。

### 让发布跟着更新走

把 `tools/update.py` 与 `tools/deploy.py` 串起来（数据没更新时 update 直接退出 0，不会空跑发布）：

```powershell
& $py -m tools.update; if ($LASTEXITCODE -eq 0) { & $py -m tools.deploy }
```

---

## 自动周期性更新

**能，但必须带 TTL，不能直接 cron 一个 `petrace.build`。** 原因是本项目所有上游 URL 都是固定的
（蛋卷 `?day=all`、中证 `endDate=20500101`、新浪 `datalen=6000`、腾讯 `count=2000`），缓存键
由 URL 决定，因此：

- 定时跑 `petrace.build`（不带 `--refresh`）→ 缓存键永不变 → **永远返回昨天的字节**，页面永不更新；
- 定时跑 `--refresh` → 每次重爬全部 52 个指数（约 9 分钟），既慢又容易踩到 WAF。

`--max-age` 解决这个矛盾：只重取已过期的响应，未过期的直接命中。**注意 `--max-age 0` 表示
「全部过期」（等价于 `--refresh`），不是「永不过期」**——代码里用 `is not None` 判断，不是真值判断。

无人值守请用 `tools/update.py`：

```powershell
& $py -m tools.update              # TTL=6h；若已是最新交易日则直接跳过
& $py -m tools.update --force      # 忽略“无新数据”跳过，强制跑一次
& $py -m tools.update --max-age 0  # 全量刷新（等价 build --refresh）
```

它比裸 `petrace.build` 多做了四件事：

1. **TTL 刷新**（默认 6h），刷新失败的 URL 自动降级到旧副本而非丢序列；
2. **智能跳过** —— A 股 15:00 收盘、上游约 18:00 后才发布日频 PE（`SETTLE_HOUR = 18`）。
   若 `manifest.as_of` 已覆盖「最近一个可能已收盘的交易日」，直接退出，不浪费上游请求；
3. **锁文件**（`logs/update.lock`）阻止重叠运行互相覆盖 `web/data`；超过 1 小时的锁视为残留并清除；
4. **真实的非零退出码**：`0` 成功（**含「无新数据」**）｜`1` build 失败｜`2` 锁被持有｜`3` 意外异常。
   这样计划任务可以据此报警，而「今天没新数据」不会被误报为故障。

### 为什么不用 Windows 计划任务

**本机用不了 `schtasks`。** 当前账号是 UAC 过滤令牌（`whoami /groups` 里 `BUILTIN\Administrators`
标注为 *"Group used for deny only"*、完整性级别 Medium），两条路径都实测被拒：

- `schtasks /create ... /sc once` → `ERROR: Access is denied.`（连用户级任务也拒；
  曾经注册过的 `PE-Trace-Refresh` 查询结果为 `ERROR: The system cannot find the file specified.`）
- `Register-ScheduledTask -Principal ... -RunLevel Limited` → `CimException: 拒绝访问。`

同时 `C:\Windows\System32\drivers\etc\hosts` 也不可写——所以任何需要提权或改 hosts 的方案都不成立。
**能写的是**：当前用户的 Startup 文件夹与 `HKCU\...\Run` 键。

### 方案：Startup 启动器 + 常驻调度器

`tools/scheduler.py` 是一个长驻循环，装在 Startup 里（**不使用计划任务**）：

```powershell
& $py -m tools.scheduler --install-startup --ensure-proxy   # 装启动器（写 .vbs 到 Startup）
& $py -m tools.scheduler --once                            # 只跑一轮，用于测试
& $py -m tools.scheduler --uninstall-startup               # 卸载
```

启动器是 `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\PE-Trace Scheduler.vbs`，
用 `pythonw.exe`（无控制台窗口）以隐藏方式跑 `-m tools.scheduler --quiet --ensure-proxy`。
调度器每交易日 **18:30（Asia/Shanghai）** 触发一次 `tools/autoupdate.py`，它自身解决四件事：

1. **补跑（catch-up）**：机器在计划时刻关机/休眠时，若 `manifest.as_of` 落后于「最近一个可能已收盘的交易日」，
   启动后立即补跑，而不是白等一天；
2. **只工作日**：周末跳过（市场休市），`tools.update` 的智能跳过仍是第二道防线；
3. **分片睡眠**：长睡眠切成 5 分钟一片，每片写心跳（`logs/scheduler.heartbeat.json`）并检查停止文件
   `logs/scheduler.stop`——出现即退出；
4. **坏一轮不死**：意外异常记日志后继续循环，只有停止文件或致命导入错误才结束进程；
5. **单实例**：`logs/scheduler.pid` 记录持有者，启动时若该 pid 仍存活就直接退出 0。
   Startup 启动器**每次登录都会触发**，没有这道闸，登录几次就会叠几个守护进程，
   每个都在 18:30 醒来抢 `web/data` 和 git 索引。
   （探活不能用 `os.kill(pid, 0)`——在 Windows 上 CPython 把非控制台信号映射到
   `TerminateProcess`，"检查"会把被查的进程杀掉；实现用 `OpenProcess` + `GetExitCodeProcess`。）

退出码：`0` 正常｜`1` 致命｜`2` Startup 注册失败。

> **`--once` 是诊断模式**：它不申请单实例锁、也不写心跳与 pid 文件，
> 只跑一轮然后退出——否则它会把常驻守护进程的心跳覆盖成自己那个几秒后就死掉的 pid。

> **`pythonw.exe` 陷阱（已修）**：`pythonw` 下 `sys.stdout` 与 `sys.stderr` **都是 `None`**。
> 原有的 `sys.stdout.reconfigure(...)` 会在启动瞬间抛 `AttributeError`，而因为 stderr 也是 `None`，
> 进程**静默退出（exit 1）且不留任何信息**——Startup 每次登录都会这样死。现在入口处与
> `petrace.core.setup_logging` 都做了 `None` 判断：日志只写 `logs/petrace.log`（文件 handler 始终有效），
> 控制台 handler 在无 stdout 时跳过。

### 发布：`tools/autoupdate.py`

调度器调用的不是 `tools.update`，而是 `tools/autoupdate.py`——它在刷新之后**自动发布到两个站点**：

- 刷新后若 `manifest.freshness.advanced == false`（没有新数据），执行 `git checkout -- web/data` 回滚，
  保持工作树干净、**不产生空提交**；
- 有新数据时 `git add web/data` → `commit` → `push origin main` → **GitHub Pages 工作流自动重新部署**；
- 仅当本次**确实推送了**（`publish()` 返回 `pushed=True`）才继续 `vercel deploy --prod`，
  否则打印「nothing published, so Vercel is already current」跳过——避免无变更时白跑一次部署；
- `--force-publish` 可在无新数据时也强制发布；`--no-publish` 只刷新不发布；
- `--no-vercel` 只发 GitHub Pages；`--ensure-proxy` 在 7897 不通时拉起 Clash Verge。

退出码：`0` 正常｜`1` 刷新失败｜`2` 发布失败｜`5` 已发 Pages 但 Vercel 部署失败｜`3` 意外异常。

> **Vercel 必须单独部署（这是它曾经停更 6 天的原因）**
> `vercel git connect` 被拒：`You need to add a Login Connection to your GitHub account first. (400)`。
> 所以 **git push 只会重部署 GitHub Pages，Vercel 与仓库没有任何关联**。
> 只 push 的话，`pe-trace.vercel.app` 会一直停留在上次手动 `vercel deploy` 的内容
> （实测：本地与 Pages 已到 `as_of 2026-10-16`，Vercel 还停在 `2026-10-09`）。
> 现在 `autoupdate.py` 在每次真正发布后调用 `deploy_vercel()`（`cwd=web/`、注入 `HTTP(S)_PROXY`），
> 并区分「整体失败」与「Pages 成功但 Vercel 失败」。

> **git 走哪条路由是动态决定的**
> 这台机器上两条路都不是恒为真，所以 `_git()` 每次先用 `_port_open(7897)` 探测再决定：
> - **代理活着 → 走代理**。`github.com` 能解析到真实 IP 但直连 TCP 直接超时
>   （实测 `Failed to connect to github.com:443 after 21106 ms`），清空代理必失败。
> - **代理已死 → 绕过代理**。此时仓库级 `http.proxy` 指向死端口，
>   不绕过会立刻 `Failed to connect ... over proxy`；而绕过代理此前能成功，
>   是因为 Steam++ 的 hosts 劫持把流量引到了本地加速器（Steam++ 一退出这条路也就没了）。
>
> 凭据走 `.secrets/gh_token.txt`（**已 gitignore**）+ `-c http.extraheader="Authorization: Basic <b64>"`，
> 不依赖 `gh` CLI，也不依赖任何常驻凭据助手。

### 手动跑一遍

```powershell
& $py -m tools.autoupdate --quiet              # 刷新 + 有新数据才发布
& $py -m tools.autoupdate --force-publish      # 强制发布
& $py -m tools.update                          # 只刷新，不发布
```

### 页面如何告诉你「更新了没有」

`manifest.freshness` 记录本次运行与上次的对比，页面顶部会据此显示一条信息条：

| 字段 | 含义 |
|---|---|
| `previous_as_of` / `previous_generated_at` | 上一次成功运行的截点与生成时间 |
| `advanced` | `true` 表示本次取得了更新的数据；`false` 表示没有（非交易日、尚未结算，或上游未更新） |
| `cache_max_age_hours` | 本次使用的 TTL；`0` 代表全量刷新 |
| `stale_responses` / `stale_urls` | 刷新失败、已回退到旧副本的请求数量与前 20 条 URL |

**`advanced: false` 不是运行失败**，而是「跑成功了，但上游还没有新数据」——这正是定时任务最常见的结果。
页面用蓝色信息条呈现这一类告示，与黄色「数据缺口」严格区分。若本次 `--only` 局部重建，
manifest 会带 `partial: true` 与 `partial_note`，避免把子集伪装成全量。

---

## 核心口径

### 滚动分位数（这是本页与多数估值仪表盘的关键区别）

多数公开估值页面给的是 **expanding（全历史）分位**——当前 PE 在「有史以来所有观测」中的位置。
本页给的是 **rolling（固定窗口）分位**：以每个观测日为终点，**按自然日回溯** `年数 × 365.25` 天，
只在**该窗口内**计算当前值的位置。

窗口用**自然日跨度**而不是「取最近 N 行」，因此日频、周频、月频序列可以用同一套规则处理，
不同频率的指数之间可以直接对比，不会因为某个源抽样更密就被动获得更长的记忆。

提供 `1年 / 3年 / 5年 / 10年 / 全历史` 五个窗口；详情页默认 **5年**（A 股与港股一个完整的
估值周期通常覆盖一轮完整涨跌，比 10 年更能反映当下环境），若样本不足则按 `3年 → 10年 → 全历史 → 1年` 退化。

### 百分位的定义：中位秩（mid-rank）

```
percentile(x) = (小于 x 的观测数 + 0.5 × 等于 x 的观测数) / 窗口内观测数 × 100
```

用 `≤` 的朴素写法（`count(v <= x) / n`）在 PE 序列上会出错：PE 常出现重复值（尤其周频、
平台期），当窗口内最高值重复出现时，该写法会把当前值直接判成 **100 分位**，制造"极度高估"的假信号。
中位秩把并列观测平分计入，是处理重复值的标准做法。

### 样本充分性

窗口内观测数须达到 `max(3, floor(回溯天数 / 该序列自身的中位间隔 × 0.6))` 才输出分位，否则记为「数据不足」。
没有这条规则，一个只有 6 个月频点的「3年窗口」也会煞有介事地给出一个分位数。

### 分位分档

| 区间 | 标签 | 颜色 |
|---|---|---|
| 0–20% | 低估 | `#1f9d55` |
| 20–40% | 偏低 | `#7cb342` |
| 40–60% | 中性 | `#c9a227` |
| 60–80% | 偏高 | `#e07b39` |
| 80–100% | 高估 | `#d64545` |

分档只是配色约定，**不含任何择时含义**。

---

## 数据源

| 源 | 内容 | 频率与深度 | 覆盖 |
|---|---|---|---|
| **中证指数公司**（官方） | 指数收盘价 + PE-TTM | **日频**；收盘自 2004，PE 多自 2011-06-28 | 19 个中证/上证系指数 |
| **蛋卷基金** danjuanfunds.com | 指数 PE/PB 历史 | **周频**；约 2016-10 起 | 38 条 |
| **乐咕乐股**（经 akshare） | 指数滚动市盈率 | **月频**；2005 起 | 7 条（仅主要 A 股宽基） |
| **multpl.com** | 标普500 滚动市盈率 | **月频**；1871 起 | 1 条 |
| **新浪财经 / 腾讯证券** | 指数日线/周线收盘价 | 日频或周频 | 价格链 |
| **ETF 价格代理** | 跟踪同一指数的 ETF 价格 | 日频 | 6 条（已标注） |

### 中证官方源的 `peg` 字段就是 PE-TTM

该接口的记录字段名为 `peg`，但它返回的是**滚动市盈率**而不是 PEG 比率。验证依据：

- 对沪深300 已知估值水位逐点核对：2015-06-12（牛市峰）**20.1**、2018-12-28（熊市底）**10.71**、
  2020-03-23（COVID 底）**11.56**、2024-02-05（底部）**10.29**、2021-10-26（阶段峰）**14.11** ——
  全部吻合 PE-TTM。若真是 PEG 比率应落在 0.5–2 区间。
- 全历史（3645 个交易日）取值范围 **8.55 … 20.38，均值 12.88**，只可能是市盈率。
- 与蛋卷 PE 在 513 个重叠交易日比对，比值 **均值 0.9656，区间 [0.8828, 1.0516]**，逐年缓慢漂移
  （2016 年 0.96 → 2019 年 0.933 → 2023 年 1.003），符合两个独立加权口径的差异特征。
- 最新交易日 2026-10-09：中证 `peg`=13.11 vs 蛋卷 PE=13.143，相差 0.25%。

**注意深度差异**：中证源收盘价可回溯到 2004 年，但 **PE 序列多自 2011-06-28 起**
（科创50 自 2020-07-06、科技龙头自 2019-03-07）。页面上 PE 与点位曲线的起点因此不同，
早于 PE 起点的价格不会被拿来计算分位。

### 中证官方 PE 序列存在单日重算跳变

中证官方的日频 `peg` 并不是一条逐日平滑的曲线：全年约有 **3%–6% 的交易日**会出现
单日 ±3% 以上的水平跳变，个别极端日达 ±20%（沪深300：2011-11-25 **−19.7%**、2012-06-08 **+16.3%**；
中证500 同类跳变更多）。这些跳变**不是行情波动**——成分股数（`consNumber`）在跳变前后不变，
收盘价也只小幅变动，跳变来源是中证对成分股盈利口径的重新校准/追溯调整。

对本项目的影响是：**日频序列的滚动分位曲线天然带有锯齿**，相邻两日分位可以相差十多个百分点
（如沪深300 在 2026-08-31 与 2026-09-01 之间由 91.3% 落到 72.7%，因为当日 PE 从 14.53 重算为 13.80）。
这不是本项目的计算缺陷，而是上游数据本身的性质。

读图时应当据此调整预期：**看趋势与区间，不要对单日分位读数做精确解读**。
多个指数叠加对比时日频序列的锯齿也会更明显；若只看大方向，可切换到周频来源（蛋卷）的指数，
或参考估值全景页的当前分位快照。

### 绝不拼接不同源的 PE 序列

同一指数常有多个源的 PE 序列，它们**永远作为独立序列并列展示，绝不首尾拼接**。
理由：不同源的 PE 水平存在系统性差异（实测沪深300 −4.2%、中证500 −17.3%、中证1000 −27.9%），
拼接会在接缝处制造一个市场上从未发生过的阶跃。

因此沪深300 页面同时显示「蛋卷(周频)」「中证官方(日频)」「乐咕乐股(月频)」三条独立序列。
详情页默认展示优先级为 **中证官方（日频）→ 蛋卷（周频）→ 最长序列**，因为日频分辨率下
滚动窗口的样本量约为周频的 5 倍，分位数更稳定。

### ETF 价格代理

少数指数只有 PE 没有免费的指数价格源，改用跟踪**同一指数**的 ETF 价格作为点位代理，
并在页面徽章与「口径说明」中明确标注（`price_note`）。代理与指数本身口径不同，
**仅可用于观察趋势形状，不能据此计算指数的绝对估值**。

当前 6 条代理：MSCI中国←MCHI、香港大盘←sz159920、标普价值←SPYV、标普质量←SPHQ、
标普红利←NOBL、MSCI印度←INDA。

---

## 覆盖情况与已知缺口

当前 52 个指数：**40 个有 PE 序列，12 个仅有点位**（截至 2026-10-09）。

### 仅有点位、无公开免费 PE 源的指数

| 指数 | 说明 |
|---|---|
| 道琼斯工业平均 | 无免费 PE 历史源 |
| 英国富时100 / 法国CAC40 / 欧洲斯托克50 / 荷兰AEX / 西班牙IBEX35 / 意大利富时MIB | 欧洲宽基均无（**德国DAX 是例外**，蛋卷提供周频 PE） |
| 日经225 / 韩国KOSPI / 台湾加权 / 澳洲标普200 | 亚太发达市场均无 |
| 创业板50 | 乐咕乐股有月频 PE 但该站当前宕机 |

已尝试并确认**不可用**的途径（勿重复尝试）：Starcapital 估值表（站点已改版，数据下架）、
TradingView scanner、Yahoo Finance、FRED、stooq、gurufocus/ycharts/investing、
eniu.com（亿牛）、worldperatio、siblisresearch、yardeni、TWSE、沪深交易所国证源
（cnindex.com.cn 全部端点异常）、`ak.index_global_hist_em`、乐咕乐股全球估值页（全站 504）。

### 两个无价格源的香港指数

**香港中小（SPHCMSHP）** 与 **香港新经济（HKHSSCNE）** 有蛋卷 PE 序列，但没有跟踪同一指数的
ETF，找不到可辩护的价格代理。这里选择**宁可缺价格，也不贴上会误导的代理线**，因此二者仅展示 PE。

### 上游可用性风险

本页依赖的上游都有明显的抗抓取行为，且**限流常常伪装成「该指数没有数据」**：

- **中证指数公司**：连续请求后会触发 WAF，返回 403 与一个无关的 HTML 页面。从远处看
  和「该指数不存在历史」几乎无法区分。本项目通过 `probe/p33_miss.py` 同一 code 用三种日期区间
  全部成功，才确认早期的「缺失」实为限流假象。
- **蛋卷**：快速轮询时，**确实有历史的指数会返回空数组**。
- **乐咕乐股**：当前整站 504（连最基础的端点也挂），非限流，需等待其恢复。
- **东方财富 push2his**：对持续轮询实施 IP 级硬封禁，已降级到价格链末位。

因此两个基础设施是必需的，不是优化：

1. **磁盘缓存 + 每主机最小间隔 + 有界指数退避**（`core.HttpClient`）。
2. **快照层**（`cache/snapshots/`）：解析后的序列按稳定名称落盘，与 URL 无关。
   上游宕机时回退到最近一次好数据，并在页面「数据缺口」中标注快照时间。
   若没有这一层，中证源被 WAF 拦截的那一刻，19 条日频 PE 序列会**静默消失**而不是报错。
3. **主机熔断**：某主机连续失败 3 次后，本轮不再尝试。没有它，一个被封锁的主机会在
   每个指数上各花掉一整个重试退避周期（约 22 秒），把 2 分钟的重建拖成 15 分钟——而数据其实已有快照。

---

## 项目结构

```
petrace/
  core.py      路径常量、磁盘缓存 HTTP 客户端（每主机限速/退避/熔断）、快照层、原子 JSON 读写
  universe.py  52 个指数的档案：名称、地区、各源代码、价格回退链、代理标注
  sources.py   上游适配器，统一输出 {"date","pe"} / {"date","close"} 形状
  metrics.py   滚动分位引擎（中位秩、自然日窗口、样本充分性规则）
  build.py     编排：抓取 → 计算 → 写出 web/data/**
web/
  index.html / style.css / app.js   三个视图：单指数明细 / 多指数对比 / 估值全景
  vendor/echarts.min.js             本地内嵌（离线可用）
  data/**                           构建产物（manifest / summary / index/*.json）
cache/
  <sha1 前2位>/<sha1>.json          原始响应缓存
  snapshots/                        解析后的序列快照（抗上游宕机）
probe/                             数据源可用性探针（历史记录，可重复运行）
tools/
  seed_csindex_snapshots.py         从中证响应缓存回填快照层
  warm_legulegu.py                  乐咕乐股恢复后预热其缓存
  update.py                         无人值守刷新入口（TTL / 智能跳过 / 锁 / 退出码）
  autoupdate.py                     刷新 + 有新数据时 git push（触发 Pages 工作流），含代理自愈
  scheduler.py                      常驻调度器：每交易日 18:30 触发 autoupdate，装入 Startup
  serve.py                          静态服务（带 Cache-Control，避免浏览器用旧前端）
  deploy.py                         发布 web/ 到 EdgeOne Makers（匿名 / API Token 两种模式）
```

生成物与运行状态（均不入库，见 `.gitignore`）：

| 路径 | 用途 |
|---|---|
| `logs/petrace.log` | 全部运行日志（`--quiet` 也写，文件 handler 始终有效） |
| `logs/update.lock` | 刷新锁，防重叠运行 |
| `logs/scheduler.heartbeat.json` | 调度器心跳：`pid` / `next_run` / `runs` / `last_rc` / `as_of` |
| `logs/scheduler.pid` | 单实例锁：持有调度槽位的 pid（进程退出时删除） |
| `logs/scheduler.stop` | 出现该文件即让调度器在下一次分片睡眠后退出 |
| `.secrets/gh_token.txt` | GitHub PAT（**已 gitignore，绝不入库**） |

## 页面的三个视图

- **单指数明细** — 该指数的滚动 PE 与点位双轴折线，可切换窗口与归一化（首点=100）；
  KPI 卡给出最新 PE、当前窗口分位、窗口中位、距窗口 PE 高点偏离。
- **多指数对比** — 勾选若干指数，把滚动分位（或 PE、归一化 PE、归一化点位）画在同一坐标系。
  不同频率的序列按日期并集对齐，缺失处留空而不是插值。
- **估值全景** — 横向条形图列出全部有 PE 的指数在当前窗口下的分位，附 20%/80% 参考线，
  可按地区筛选，下方为可排序的明细表。

## 复现与校验

```powershell
# 数据源可用性探针（历史上用于确认各项结论，可重复运行）
& $py probe\p34_cov2.py      # 中证覆盖度（含限流感知重试）
& $py probe\p38_unused.py    # 蛋卷未使用的指数清单
& $py probe\p39_devpe.py     # 发达市场 PE 源候选

# 从已有响应缓存回填快照层（不联网）
& $py tools\seed_csindex_snapshots.py
```
