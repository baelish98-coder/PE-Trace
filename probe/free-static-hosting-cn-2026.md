# 2026 年中国大陆可用的免费静态网站托管方案研究报告

调研时间：2026-10-10（Asia/Shanghai）
目标场景：7.5 MB 静态站点（HTML/CSS/JS + ECharts vendor bundle + ~52 个 JSON 数据文件），**每日更新**（本地 Python 脚本重建 JSON 后发布），主要受众在**中国大陆**。

---

## 0. 结论速览

| 排名 | 方案 | 一句话结论 |
|---|---|---|
| 🥇 首选 | **GitHub Pages** | 免费额度够用、Actions 全自动部署、自定义域名+HTTPS 免费、**上海移动实测 20/20 全 200，平均 0.47 s**（本次实测最快的境外静态托管） |
| 🥇 并列首选 | **腾讯 EdgeOne Makers** | 唯一官方宣称「永久免费 + 含中国大陆加速」的 CDN/静态托管，无限流量、大陆实测 0.34–0.75 s；**但大陆加速区域必须 ICP 备案**，无备案只能选「全球可用区（不含中国大陆）」 |
| 🥈 稳健备选 | **Cloudflare Pages** | 免费额度最宽松（500 构建/月、20k 文件、100 自定义域名），大陆实测平均 1.03 s，Direct Upload 纯 CLI 无需浏览器登录 |
| 🥈 稳健备选 | **Surge.sh** | 部署最简单（一条命令 + Token，CI 里零交互），免费含自定义域名与自动签发证书；大陆实测 0.31–1.45 s |
| ⚠️ 可用但需注意 | **Render** | 静态站免费、自动 TLS，但大陆实测最慢（render.com 平均 3.87 s） |
| ⚠️ 可用但需注意 | **GitLab Pages / Codeberg Pages** | 免费且支持自定义域名，但 gitlab.io 实测不稳定（同一域名 6/6 返回 301、另一轮 3/3 超时） |
| ❌ 不可用 | **Vercel (`*.vercel.app`)** | 大陆 **DNS 污染**，6/6 全超时；只有绑自定义域名才可能可用，且 Hobby 计划**禁止商用** |
| ❌ 不可用 | **Netlify Free** | 2026 已改 credit 制：每日部署 15 credits × 30 天 = 450 > **300 credits/月硬上限** → 每日更新场景直接超额 |
| ❌ 已停服 | **Gitee Pages** | **2026 年确认已死**（详见 §2.5 证据链） |
| ❌ 被墙 | **Neocities** | 上海移动实测 `Connection was reset`（RST） |
| ❌ 不适用 | **Zeabur Free** | 免费档不含托管算力，只能纳管「你自己的服务器」 |
| ❌ 成本陷阱 | **腾讯云 COS / 阿里云 OSS** | 免费额度只抵「存储」，**下行流量必付**，每日被访问站点不适用 |
| ❓ 信息缺口 | **SourceForge Pages** | 官方文档被 Cloudflare 人机挑战拦住，**无 2025-2026 官方证据** |

**针对本项目的最终建议**：
- **主站 → GitHub Pages**（仓库 + Actions 自动部署）+ 自定义域名；
- 若追求大陆极致速度且**已有 ICP 备案域名** → **EdgeOne Makers**；
- **每日发布脚本最省事的组合** → Cloudflare Pages Direct Upload 或 Surge.sh（一条 CLI 命令、Token 鉴权、零浏览器交互）。

---

## 1. 评测口径与方法

### 1.1 四项必答指标
对每个平台均回答：
1. **免费额度**（构建次数、带宽、存储、文件数/单文件大小、项目数）
2. **能否脚本化部署**（CI/CLI，无需每次浏览器登录）
3. **自定义域名 + 免费 HTTPS**
4. **中国大陆可达性**（附实测证据）

### 1.2 证据等级
- **A 级（官方原文）**：直接抓取厂商官方文档/定价页正文，标注 URL 与页面更新时间。
- **B 级（本机实测）**：测点 = 上海移动，出口 IP `183.195.101.95`，时区 Asia/Shanghai。方法：`curl -o NUL -w "%{http_code} %{time_total}"` 多次采样。
  - **重要校正**：本机 `hosts` 文件把 `github.io / github.com / raw.githubusercontent.com` 等劫持到 `127.0.0.1`（本机加速工具所致），直接请求会得到**假阴性**。凡涉及 GitHub 域名的实测均使用 `curl --resolve <host>:443:<真实IP>` 绕开 hosts。
- **C 级（第三方节点）**：`check-host.net` 海外节点，用于「中国大陆数据源能否从**美国**访问」这一问题。
  - **已知局限**：check-host.net 全站 57 个节点中**没有任何中国大陆节点**（仅有 hk1 香港），因此**不能**用它证明「中国大陆可达性」；中国大陆结论一律由 B 级本机实测承担。
  - 该站 HTTP 批量检查 API 多次返回空结果（`nodes:{}` / 404 页），故仅采用其单域名 + 少节点的成功结果。

### 1.3 中国大陆网络环境校准（证明测点为真实大陆网络）
| 目标 | 结果 | 含义 |
|---|---|---|
| google.com | 超时 | 典型大陆环境 |
| youtube.com / facebook.com / twitter.com | SSL 失败 | 被墙 |
| x.com | 超时 | 被墙 |
| wikipedia.org | 超时 | 被墙 |
| openai.com | 403 | 被墙/风控 |
| baidu.com / qq.com / taobao.com / bing.com / unpkg.com | 200 | 境内正常 |

---

## 2. 逐平台详报

### 2.1 GitHub Pages ✅ 首选

**免费额度（官方原文）**
来源：<https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits>（页脚 GitHub Inc. © 2026）

| 项目 | 限制 |
|---|---|
| 源仓库大小 | **推荐 ≤ 1 GB** |
| **已发布站点大小** | **不得超过 1 GB** |
| 部署超时 | **10 分钟** |
| 带宽 | **软上限 100 GB/月** |
| 构建频率 | **软上限 10 builds/hour**；官方原文：「This limit does not apply if you build and publish your site with a custom GitHub Actions workflow」→ **用 Actions 工作流可绕开该构建限额** |
| 站点数量 | 每个账号只能建**一个** user/org site（项目站点不限） |
| 可用性 | **public 仓库**：GitHub Free 可用；**private 仓库**需 Pro/Team/Enterprise |

**禁止用途（官方原文）**：不得作为「free web-hosting service to run your online business, e-commerce site, or any other website that is primarily directed at either facilitating commercial transactions or providing commercial software as a service (SaaS)」。→ 本项目为基金数据研究展示，**非商业交易/非 SaaS，合规**。

超额后果：可能停止服务，或收到 GitHub Support 邮件建议加第三方 CDN / 改用其他服务；速率限制可返回 HTTP 429。

**① 脚本化部署：支持（且是最强的一种）**
官方自定义工作流（来源：<https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages>）：
- `actions/configure-pages@v5`
- `actions/upload-pages-artifact@v4` —— artifact 必须是 **gzip 压缩的单个 tar**，**必须 < 10 GB**，不得含软/硬链接
- `actions/deploy-pages@v4` —— 需 `needs` 指向 build job id，需 environment（默认 `github-pages`）
- 支持 build/deploy 同 job 或分离 job

**Actions 计费（官方原文）**：「**GitHub Actions usage is free for self-hosted runners and for public repositories that use standard GitHub-hosted runners**」→ **public 仓库分钟数完全免费**；Actions cache 独立配额 10 GB/repository。

→ 对「每日更新」：本地 Python 重建 JSON → `git commit && git push` → Actions 自动构建并发布，**零人工、零浏览器登录**。

**② 自定义域名 + HTTPS：支持，免费**
来源：<https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/about-custom-domains-and-github-pages>
- 子域用 **CNAME**，根域（apex）用 **A / ALIAS / ANAME**
- 同时配置 apex 与 www 时，GitHub Pages **自动在两者间做重定向**
- 证书自动签发，控制台可勾选「Enforce HTTPS」
- **注意**：新配自定义域名后证书签发需要一定时间；若 DNS 有 CAA 记录需允许 Let's Encrypt/DigiCert

**③ 中国大陆可达性：✅ 快**
| 测试对象 | 结果 |
|---|---|
| `google.github.io`（185.199.108.153） | **200 / 0.23–0.49 s** |
| `microsoft.github.io`（185.199.109.153） | **200 / 0.22–0.51 s** |
| `pages.github.com`（--resolve 185.199.108.153） | **200 / 0.24–0.65 s** |
| `sindresorhus.github.io` | 301（正常，站点配置了跳转） |
| **稳定性：google.github.io × 20 次** | **20/20 全部 200，平均 0.47 s（最大 1.34 s）** |

**⚠️ 本机特殊问题（必须告知用户）**：这台机器的 `hosts` 文件把 `github.io / github.com / api.github.com / raw.githubusercontent.com / objects.githubusercontent.com / github.dev` 全部劫持到 `127.0.0.1`。因此：
- 本机直接访问 GitHub Pages 会**失败**（假阴性），需修 hosts 或用 `curl --resolve`；
- 但**最终访客（其他大陆用户）不受影响**——实测真实 IP 可达且快。

---

### 2.2 腾讯 EdgeOne Makers（原 EdgeOne Pages）✅ 大陆首选（若已备案）

**免费额度（官方原文）**
来源：<https://pages.edgeone.ai/zh/document/limits-and-quotas>（标题「EdgeOne Makers 免费版配额详解」）

| 项目 | 免费版配额 |
|---|---|
| 项目数 | **40 个** |
| **总存储容量** | **5 GB**（按站点统计，站点下所有项目合计） |
| 单项目文件数 | **20,000** |
| 单文件大小 | **25 MB** |
| 构建次数 | **500 次/月**（按开通 Makers 服务日期重置） |
| 并发构建 | **1** |
| 单次构建超时 | **20 分钟** |
| 构建算力 | **4 核 6 GB** |
| **自定义域名** | **200 个** |
| **免费 SSL 证书** | **支持** |
| 流量/请求 | **不限量**（免费版核心权益：「不限量的网站安全加速流量与请求额度」） |

函数/存储类：Edge Functions 300 万次/月、CPU 300 万 ms/月；Cloud Functions 100 万次/月、50 万 GB-s/月；KV 1 GB；Blob 1 GB。安全：自定义规则 4 条、精准速率限制 1 条、**流量防盗刷「仅适用中国大陆地区」**、基础 Bot 管理。

官方稳定性声明：「EdgeOne Makers 目前提供【免费版】……本文列出的均为免费版当前生效的各项配额」「**免费版配额在商业化正式上线前执行较为宽松，用量超限也会优先保障您的业务稳定**；额度不足可提交工单申请提额」。

**免费政策（官方原文）** 来源：<https://pages.edgeone.ai/pricing>
- 「**Free: Deploy Web Apps and AI Agents at zero cost – our free plan is permanently available!**」$0/month
- FAQ：「Will the Free plan be available long-term? **Yes, our Free plan is here to stay and will be available permanently!**」
- 「**Before the paid version launches, your service will not be interrupted even if you exceed the free tier limits.**」
- 首页 banner：「🎉 EdgeOne Free Plan Launches! **The World's First Free CDN with China Access**」
- 节点规模（官方 FAQ）：「全球超过 **3200+ 个边缘节点**（其中亚洲超 2500+）」

**① 脚本化部署：支持**
来源：<https://pages.edgeone.ai/zh/document/edgeone-cli>、<https://pages.edgeone.ai/zh/document/using-github-actions>
- `npm install -g edgeone`；命令命名空间已由 `edgeone pages` 升级为 **`edgeone makers`**（旧命令过渡期仍可用，不会立即下线）
- **`-t, --token`：用于 CI/CD 或非交互环境的 API Token；已登录时可省略** → 明确支持无浏览器登录
- 官方 GitHub Actions 工作流：仓库 Secrets 设 `EDGEONE_API_TOKEN`，核心步骤
  ```
  npx edgeone makers deploy <outputDirectory> -n <projectName> -t ${{ secrets.EDGEONE_API_TOKEN }} [-e <env>]
  ```
  官方 yaml 使用 `runs-on: ubuntu-latest` + `actions/checkout@v4` + `actions/setup-node@v4`（node `'22.11.0'`）；另有 PR 预览部署示例（`pull_request_target` + 回写评论）
- SDK：`makers.deployments.deploy` 支持三种 artifact（键值对内容、本地目录、本地 Zip）；**不读 `.gitignore`**、**拒绝符号链接**；文档导航含「使用 Gitlab CI/CD」「使用 CNB 插件」

**② 自定义域名 + HTTPS：支持，但有两大前提**
来源：<https://pages.edgeone.ai/zh/document/custom-domain>、<https://pages.edgeone.ai/zh/document/configuring-an-https-certificate>、`eo-domain-overview2.txt`

**(a) ICP 备案硬约束（官方原文）**：
> 「**当项目加速区域为"中国大陆可用区"或"全球可用区（含中国大陆）"时添加的域名需先在工信部完成备案。**」
> 「选择加速区域为**全球可用区（不含中国大陆）**时……添加自定义域名**不要求工信部备案**。」

→ 三档加速区域：`中国大陆可用区`（需备案）、`全球可用区`（需备案）、`**全球可用区（不含中国大陆）**`（**无需备案**）。无备案者只能选第三档，流量走境外/港澳台节点，无法进入大陆节点。

**(b) HTTPS 证书不会自动分配（官方原文，重要区别）**：
> 「**Makers 不会自动为您的域名分配 HTTPS 证书**，但鉴于安全性，可信度，搜索排名等因素我们强烈建议您完善 HTTPS 配置。」

两种补救：① 申请免费证书（来源 **Trust Asian / Let's Encrypt 的 RSA 证书**，自动申请、部署、续签）② 使用 SSL 托管证书（上传至腾讯云 SSL 控制台，最多同时部署一本 RSA/ECC/SM2）。支持强制 HTTPS（301/302）、HSTS、OCSP 装订。
→ 即**可以做到免费 HTTPS，但需手动开启一次**，不像 GitHub Pages / Cloudflare Pages 那样默认自动。

**(c) 项目/部署域名的特殊限制（官方原文）**：
> 「中国大陆网络环境：须使用系统生成的预览链接进行访问，该链接有效期为 **3 小时**，超时后返回 **401**」
> 「非中国大陆网络环境可直接访问。建议绑定自定义域名以建立稳定访问通道」

→ **结论：免费默认域名（`*.edgeone.app`）在中国大陆不能作为长期稳定入口**，必须绑自定义域名。这是本项目最关键的一条注意事项。

**③ 中国大陆可达性：✅ 最快**
| 测试对象 | 结果 |
|---|---|
| `edgeone.ai`（43.168.19.103） | **200 / 0.34–0.75 s**（6/6） |
| `pages.edgeone.ai` | **200 / 0.69–1.11 s** |
| `edgeone.app`（43.168.176.154） | **302 / 0.519 s** |
| `www.edgeone.app` / `demo.edgeone.app` | 404 / 0.498 s、0.766 s（解析与 TLS 正常，仅该主机无内容） |

---

### 2.3 Cloudflare Pages ✅ 综合最优免费额度

**免费额度（官方原文）**
来源：<https://developers.cloudflare.com/pages/platform/limits/>（页面标注 Last updated **Sep 5, 2026**）

| 项目 | Free | Pro | Business |
|---|---|---|---|
| 并发构建 | **1** | 5 | 20 |
| **构建次数** | **500/月** | 5,000 | 20,000 |
| 构建超时 | 20 分钟 | | |
| **文件数/站点** | **20,000** | 100,000（需设 `PAGES_WRANGLER_MAJOR_VERSION=4`） | |
| **单文件最大** | **25 MiB**（更大建议放 R2） | | |
| **自定义域名** | **100/项目** | 250 | 500 |
| Preview 部署 | 无限 | | |
| 项目上限 | **100/账号**（「not routinely increased」） | | |
| 新账号限制 | 创建后**前 48 小时**创建项目数受限（防滥用） | | |

`_headers` ≤100 条（单条 ≤2,000 字符）；`_redirects` ≤2,000 静态 + 100 动态。

**① 脚本化部署：支持（两条路）**
来源：<https://developers.cloudflare.com/pages/get-started/direct-upload/>（Last updated Apr 21, 2026）
- **Direct Upload / Wrangler CLI**：`npx wrangler pages project create` → `npx wrangler pages deploy <BUILD_OUTPUT_DIRECTORY>`
  - **Wrangler 不接受 zip，只接受单目录**（拖拽方式才支持 zip）
  - **限额差异**：Wrangler **20,000 files / 25 MiB**；拖拽 **1,000 files / 25 MiB**
  - 预览部署：`--branch=<BRANCH_NAME>` → `<BRANCH>.<project>.pages.dev`
  - `pages project list --json` 可脚本化
  - **「You cannot switch to Git integration later」** —— 选了 Direct Upload 就不能再改 Git 集成（只能新建项目）。**决策前必须想清楚**。
- **Git 集成**：push 自动构建（但会占用 500 次/月构建额度）

→ 对「本地 Python 重建 JSON 后发布」：**Wrangler Direct Upload + API Token 是最贴合的路径**（不依赖 git、不消耗构建额度、纯命令行）。

**② 自定义域名 + HTTPS：支持，免费自动**
自定义域名上限 100/项目，证书由 Cloudflare 自动签发与续期。

**③ 中国大陆可达性：✅ 可用（中等偏快）**
| 测试对象 | 结果 |
|---|---|
| `pages.dev`（104.18.20.135） | 301 / 1.03 s |
| **`hugo.pages.dev` × 20 次** | **20/20 全 200，平均 1.029 s** |
| `tailwindcss.pages.dev` | 522（Cloudflare 侧错误，非网络问题） |

**⚠️ Cloudflare 中国网络的真实情况（避免误解）**
来源：Cloudflare 官方文档（`cf-china-network.txt`）
- Cloudflare China Network = 「running selected Cloudflare performance and security products on data centers located in Mainland China, operated by Cloudflare's partner **JD Cloud**（京东云）」
- **「The Cloudflare China Network is available as a separate subscription for customers on an Enterprise plan」** → **Enterprise 专属，免费计划无法享用**
- **「You must have a valid ICP (Internet Content Provider) filing or license for each apex domain you wish to onboard to Cloudflare」**

→ **免费 Cloudflare Pages 的 `*.pages.dev` 或自定义域名走的是 Cloudflare 全球 Anycast 网络（通常就近落到香港/新加坡/洛杉矶），并非中国境内节点。** 实测 1.03 s 属「可用但不快」，且受跨境链路波动影响。

---

### 2.4 Netlify ❌ 每日更新场景额度不够

**免费额度（官方原文）** 来源：<https://www.netlify.com/pricing/>（2026 已改为 **credit 制**）
- 「Build and deploy free forever」「**300 credit limit / month**」「The free plan is always free, with **hard monthly limits that cannot be exceeded** or incur any costs」
- 计费单价：
  | 项目 | credit 消耗 |
  |---|---|
  | **Production deploys** | **15 credits / 次** |
  | Compute | 10 credits / GB-hour |
  | **Bandwidth** | **20 credits / GB** |
  | Web requests | 2 credits / 10k requests |
- Pro：1,000 credits/月起（可选 3,000 / 5,000 / 10,000 / 15,000 / 20,000 档），加购 $5/500 credits、$10/1,500 credits
- Free/Personal 计划**仅 1 member**，不能加席位；开源项目可申请 Open Source plan

**关键计算（本项目杀手）**：每日部署 × 30 天 = `15 credits × 30 = 450 credits` **> 300 credits/月硬上限** → **免费额度在第 20 天左右就被击穿**。若再算带宽（20 credits/GB），7.5 MB 站点每 GB 访问量消耗更高。

**① 脚本化部署：支持**（`netlify deploy` CLI 与 Deploy API 均有官方文档，`netlify-cli-doc.txt` / `netlify-deploy-api.txt`）

**② 自定义域名 + HTTPS：支持**（Let's Encrypt 自动签发）

**③ 中国大陆可达性：✅ 可用**
| 测试对象 | 结果 |
|---|---|
| `netlify.app`（13.215.239.219） | 301 / 0.33–0.69 s |
| **`reactjs.netlify.app` × 20 次** | **20/20 全 200，平均 0.718 s**（本次实测第二快） |
| `vite.netlify.app`（52.74.6.109） | 200 / 1.59 s |

**结论：网络表现优秀，但 2026 的 credit 定价模型与「每日更新」需求正面冲突，不推荐作为本项目主力托管。**

---

### 2.5 Gitee Pages（码云 Pages）❌ 已确认停服

> 用户特别强调「don't guess」其当前状态，以下是完整证据链。

| 证据 | 内容 |
|---|---|
| **官方文档站点地图** | `help.gitee.com/sitemap.xml` 完整下载（114,586 字节，**735 个 URL**）→ **含 "page" 的 URL 数量 = 0**。一级路径仅：开发协作 / account / account-and-profile / ai-productivity / base / blog / category / change-log / chat / cla / community / devops / enterprise / Git 知识大全 / gitee-go / ide-plugin / issue / license / pull-request / questions / repository / services / services-third-party / tags / terms / webhook —— **完全没有 pages 类目** |
| **帮助中心首页** | 导航仅「开源软件 / 企业版特惠 / 高校版 / 私有云 / 登录 / 注册」，内容板块为 AI 助手、企业账户、项目文档、代码管理、流水线、效能度量、产品动态 —— **无 Pages** |
| **深链探测** | `help.gitee.com/repository/gitee-pages` → **404**；`gitee.com/help/articles/4136`（旧 Pages 文档）→ 301 后内容变为帮助中心首页（**原文已下线**） |
| **域名实测** | `gitee.io`（106.13.251.3，中国 IP）→ **TCP 443 不通，3/3 全部 000 超时**；对照 `gitee.com` 本身 200 / 1.12–1.16 s 正常 → **Pages 服务域名已不再提供服务** |
| **社区共识** | 多方指向 2024-07-15 起 Gitee Pages 停止服务 |

**结论：Gitee Pages 在 2026 年已不可用。官方文档体系无此条目 + 服务域名 TCP 层不通 + 旧文档被重定向至首页，三重证据一致。**

---

### 2.6 Surge.sh ✅ 部署最简单的选项

**免费额度（官方原文）** 来源：<https://surge.sh/pricing>（© 2026 Chloi Inc.）
- Free：「Surge is free to use」「**Unlimited publishing**」「Custom domain」「**Basic SSL**」
- Professional **$30/mo**：Custom SSL、CORS、Custom redirects、Password protection 等

**① 脚本化部署：支持（最干净的一种）**
来源：<https://surge.sh/docs/cli/automation>、<https://surge.sh/docs/api>
- `npm install --global surge`（**需 Node.js 18+**，CLI 0.44.1）
- **Token 铸造**：`surge tokens add --domain example.com -m "ci"` → 存入 CI secret 作 `SURGE_TOKEN` → CLI 自动读取，**pipeline 内无需登录**
- **「Tokens never face a two-factor challenge」**（CI 里绝不会卡 2FA）；`--domain` 限定作用域；`surge tokens rem <id>` 吊销
- **「If a required value is missing and there's no TTY to ask on, the command aborts rather than hangs」** → 无 TTY 时快速失败而非挂起，对 CI 友好
- 官方文档直接给出 GitHub Actions yaml：`actions/checkout@v4` + `actions/setup-node@v4`（node 20）→ `npx surge ./dist example.com`，env `SURGE_TOKEN`
- **HTTP API**：Base URL `https://surge.surge.sh`；**Basic 认证，用户名固定为字面量 `token`，密码为 API token**；`PUT /<domain>` 直接传 tarball：
  ```
  tar czf - -C ./my-site . | curl -X PUT https://surge.surge.sh/<domain> \
    -u token:<API_TOKEN> -H "Content-Type: application/gzip" --data-binary @-
  ```
  另有 `GET /list`、`DELETE /<domain>`；deploy/certificate 端点用 NDJSON 流式返回
- 部署语法：`surge <project> <verb>`；`surge ./dist example.com` 首发后会在 `dist/CNAME` 记录域名，之后 `surge publish` 无需参数；rollback 是**指针切换（秒级）**

**② 自定义域名 + HTTPS：支持，免费**
来源：<https://surge.sh/docs/platform/custom-domains>、<https://surge.sh/docs/cli/ssl>
- **「Every project on Surge can live at your own domain, free—certificate included.」**
- 三种接入：① **委派 NS**（`ns1–ns4.surge.world`，推荐，覆盖根域 + 全部子域 + 通配证书）② CNAME `geo.surge.world`（geo-aware；根域需 ALIAS/ANAME/flattened CNAME）③ A 记录 `138.197.235.123`（**单区域固定，非 geo-aware**）
- `surge example.com debug status` 三态：`waiting on dns` / `securing` / `live`
- **「Once the domain resolves to Surge, a free managed certificate is provisioned automatically and renewed before it expires」**
- **「Every project on Surge is served over HTTPS」**；强制 HTTPS 跳转写法 `surge ./dist https://example.com`
- 自带证书（`surge example.com ssl --pem ./example.com.pem`）**需付费计划**

**⚠️ 一处官方口径矛盾（报告如实标注）**：定价页把「Force http to https」列为 Professional 付费功能，但 **CLI/SSL 文档明确写出强制 HTTPS 的方式且未标付费**。以文档为准；实际使用前建议在免费账号上验证。

**③ 中国大陆可达性：✅ 可用**
| 测试对象 | 结果 |
|---|---|
| `surge.sh`（172.104.96.133 / 45.55.110.124） | **200 / 0.31–1.45 s，6/6 全 200** |

---

### 2.7 Vercel ❌ `*.vercel.app` 在大陆被 DNS 污染

**免费额度（官方原文）** 来源：<https://vercel.com/docs/plans/hobby>
- Hobby 免费，面向「developers with personal projects, and small-scale applications」
- 额度：Fast Data Transfer **100 GB**；Fast Origin Transfer 10 GB；CDN Requests **1,000,000**；Function Invocations 1,000,000；Image Transformations 5,000；Global Config Reads 100,000；Writes 100；Active CPU 4 CPU-hrs；Provisioned Memory 360 GB-hrs
- **超出后需等 30 天才能再次使用该功能**（无计费周期概念）
- **关键限制**：「As stated in the fair use guidelines, the **Hobby plan restricts users to non-commercial, personal use only**.」→ **仅限非商业个人用途**
- 其他：Hobby Projects 200；**Domains per project 50**；**Deployments per day 100**；Build 2 vCPU / 8 GB 内存
- `vercel-cli.txt` 已确认 CLI 部署路径存在

**① 脚本化部署：支持**（`vercel` CLI / API，Token 鉴权）

**② 自定义域名 + HTTPS：支持**（自动签发）

**③ 中国大陆可达性：❌ `*.vercel.app` 被污染**
| 测试对象 | 结果 |
|---|---|
| `vercel.app`（184.173.136.86） | **000 超时（6/6 全失败）** |
| `nextjs-vercel.vercel.app`（199.59.149.210） | **000** |
| `react.vercel.app`（185.45.7.185） | **000** |
| **DNS 交叉验证** | 8.8.8.8 / 1.1.1.1 / 223.5.5.5 均返回 `2a03:2880:...:face:b00c:...` —— **Facebook 特征 IPv6 段 → 典型 DNS 污染**；114.114.114.114 返回 174.37.54.20 |
| 对照 | `vercel.com` **200 / 5.96 s**、`nextjs.org` 200 / 1.81 s、`hyperui.dev` 200 / 1.34 s → **平台本身可达，只有 `*.vercel.app` 默认域被污染** |

**结论**：必须绑定自定义域名才可能可用；叠加「Hobby 禁止商用」限制，本项目不推荐。

---

### 2.8 腾讯云 COS 静态网站托管 ❌ 成本陷阱

来源：<https://cloud.tencent.com/document/product/436/6240>（最近更新 **2026-08-27**）
- 面向**新用户**（首次开通 COS）：个人 **50 GB 标准存储容量包**（企业 1 TB），有效期 **6 个月（180 天）**
- **免费额度仅可抵扣「标准存储容量」** —— **不可抵扣外网下行流量、请求次数、CDN 回源流量等**
- 价格示例：外网下行流量 **0.5 元/GB**；请求 0.01 元/万次；存储 0.118 元/GB/月
- 仅适用公有云地域（不含金融云）

**结论：一个每日被访问的静态站点，下行流量费用必然发生（例如 10 GB/月 ≈ 5 元/月），且 180 天后连存储也开始计费。对本项目不适用。**
可达性（境内，无需担心）：`cos.ap-shanghai.myqcloud.com`（39.145.23.100/27.159）→ 403 / **0.425 s**（403 为无 bucket 的正常响应）。

---

### 2.9 阿里云 OSS 静态网站托管 ❌ 成本陷阱

来源：<https://help.aliyun.com/zh/oss/product-overview/free-quota-for-new-users>（标题「新用户免费试用额度-对象存储(OSS)」）
- 领取条件：**完成阿里云账号实名认证，但尚未开通 OSS 服务**
- 额度：**标准-本地冗余存储包 20 GB / 3 个月 + 下行流量包 2 GB / 3 个月 + 请求包 20 万次 / 3 个月**（适用全部地域）
- 仅抵扣「标准存储（本地冗余）容量 / API 请求 / 外网流出流量」三类；低频访问、图片处理等**不可抵扣**
- **叠加规则**：存储可叠加地域 = 中国香港、美（硅谷/弗吉尼亚）、新加坡、马来西亚、印尼、菲律宾、泰国、日本、韩国、德国、英国、阿联酋；流量可叠加地域 = 中国香港、新加坡、印尼、泰国、美（弗吉尼亚/硅谷）、日本、韩国 —— **中国大陆各地域不在任一叠加列表内**
  → 中国大陆 bucket 只能拿 **20 GB 存储 / 2 GB 流量 / 3 个月**，之后按量计费

**结论：与 COS 同构——免费额度只覆盖极前期小流量，3 个月后失效，每日被访问站点不适用。**
可达性（境内）：`oss-cn-hangzhou.aliyuncs.com` → 403 / **0.073 s**；`cn-hangzhou.oss.aliyuncs.com` → 403 / **0.089 s**（极快）。

---

### 2.10 Render ⚠️ 免费但大陆偏慢

来源：<https://render.com/docs/static-sites>、<https://render.com/docs/free>
- **「Static sites are fast and free to deploy.」** 连 Git 仓库后每次 push 自动更新；每站得到唯一 `onrender.com` URL
- 静态站点**同计** workspace 月度 outbound bandwidth 与 pipeline minutes 配额
- 免费计划覆盖 Web services / Render Postgres / Render Key Value + **静态站点**
- **「Free instances have important limitations... Do not use them for production applications.」**（该警告上下文针对 free **instance** 计算型服务；静态站点单独免费）
- **HTTPS 免费自动**：「Render uses Let's Encrypt and Google Trust Services to automatically issue and renew TLS certificates for every site and service. There is no additional setup, and **TLS certificates are always included for free**.」
- **「Add custom domains to your static site for free.」** 免费 DoS 防护

**① 脚本化部署**：Git push 触发（可用 CI 推送到 Git 仓库）；官方另有 API/Blueprint
**② 自定义域名 + 免费 HTTPS**：✅
**③ 中国大陆可达性：⚠️ 可用但最慢**
| 测试对象 | 结果 |
|---|---|
| `onrender.com`（34.83.64.96） | 301 / **2.11 s** |
| `render.com` | 200 / **2.91–5.33 s，6/6 全 200，平均 3.87 s**（本次实测最慢） |

---

### 2.11 Zeabur ❌ 免费档不含托管算力

来源：<https://zeabur.com/pricing>
- **Free $0/月** 内容仅为：「Dashboard basics and community support」「Manageable own servers: **1**（Servers you purchased and own elsewhere... not bought from Zeabur, but you can still manage them from the Zeabur dashboard）」、Build CI spec **2C4G**、Log retention **48h**、单文件上传上限 **50 MB**
- Dev $5/月（前 14 天免费）→ 自有服务器 3 个、日志 7 天、单文件 250 MB；Pro $19/月；Team $79/月（含 3 席位）

**结论：Zeabur Free 不提供免费运行算力，只能纳管「你自己购买的服务器」→ 对本项目不适用。**
可达性：`zeabur.app`（54.219.66.111）→ 404（域名可解析，仅该主路径无内容）。死胡同：`zeabur.com/docs/en-US/get-started/free-plan` → 404。

---

### 2.12 SourceForge Pages ❓ 信息缺口

- 官方文档页 `sourceforge.net/p/forge/documentation/Project%20Web%20Pages/` → **HTTP 403 + Cloudflare 人机挑战页**（「Just a moment... Enable JavaScript and cookies to continue」），curl 无法读取正文
- 网络层可达：`sourceforge.net` 200 / 1.58–3.55 s（104.18.12.149）；`sourceforge.io` 301 /（104.18.10.31）
- **诚实标注：未能取得 2025-2026 官方证据证明 SOURCEFORGE PAGES 仍作为免费静态托管存在。列为信息缺口，不作为推荐。**

---

### 2.13 Neocities ❌ 中国大陆被墙

- 免费档：**1 GB 存储 / 200 GB 带宽**（来源：<https://neocities.org/supporter> 对比表；Wikipedia 词条亦佐证「It offers 1 GB of storage space, 200 GB of bandwidth for free sites and no server-side scripting for both paid and free subscriptions」）
- 商用静态托管；免费与付费档**均无服务端脚本**
- **中国大陆可达性：❌ 被墙** —— `neocities.org`（23.143.32.4）`curl -v` 明确报 **「Recv failure: Connection was reset」**（TCP RST）

---

### 2.14 Codeberg Pages ⚠️ 技术可行，但生态与稳定性需权衡

来源：<https://docs.codeberg.org/codeberg-pages/using-custom-domains/>
- 官方明确警示：**「Codeberg Pages has recently migrated from the legacy v2 codebase to the newer git-pages codebase」**；**「Pages Server v2 has already been disabled for new users due to abuse」**（老用户仍可用）
- 自定义域名：CNAME（`codeberg.page.`）/ ALIAS / A 记录 `217.197.84.141` + AAAA `2a0a:4580:103f:c0de::2`
- **授权机制**：需在域名上配置 TXT 记录证明仓库有权部署 —— webhook 方式用 `_git-pages-repository.<domain>`；**Forgejo Actions** 方式用 `_git-pages-forge-allowlist.<domain>`，值填仓库 HTTPS clone URL
- **首部署必须用 `http://`**：「It is not possible to issue SSL certificates for domains that have not been previously deployed」→ 首次成功后再改 `https://`
- CAA 记录需显式允许 Let's Encrypt（含 staging）
- **① 脚本化部署：✅**（webhook / Forgejo Actions）
- **② 自定义域名 + 免费 HTTPS：✅**（Let's Encrypt，需先 HTTP 首部署）
- **③ 大陆可达性：✅** `codeberg.page`（217.197.84.141）→ **200 / 2.30 s，6/6 全 200**

---

### 2.15 GitLab Pages ⚠️ 免费可用，但默认域实测不稳定

来源：<https://docs.gitlab.com/user/project/pages/>（Tier: **Free, Premium, Ultimate**）
- 「Run on GitLab-provided infrastructure at **no additional cost**」「Connect with custom domains and SSL/TLS certificates」
- **「If you're using GitLab Pages default domain (`.gitlab.io`), your website is automatically secure and available under HTTPS.」**
- 部署方式：仓库内 `.gitlab-ci.yml` 中带 `pages: true` 的 job；默认发布 `public/` 目录（可自定义）；支持 `pages.expire_in`、并行部署、Primary domain（308 重定向）、unique domains（默认开启，防同 group 项目共享 cookie）
- 支持任意静态生成器（Hugo/Jekyll/Gatsby/Hexo…）与纯 HTML/CSS/JS/Wasm；**不支持 `.php`/`.asp` 等服务端处理**
- **① 脚本化部署：✅**（GitLab CI/CD）
- **② 自定义域名 + 免费 HTTPS：✅**（Let's Encrypt 自动获取与续期）
- **③ 大陆可达性：⚠️ 不稳定**
  | 测试对象 | 结果 |
  |---|---|
  | `gitlab.io`（104.21.96.56 / 172.67.173.75） | 6/6 **全部返回 301**（非 200）；另一轮直连 **3/3 出现 000 / 15 s 超时** |
  | `gitlab-org.gitlab.io`（35.185.44.232） | 302 / 1.84 s（可达） |

  → `gitlab.io` 本身是 apex 重定向域，**不能直接作为站点根域**；用户站是 `<user>.gitlab.io`。稳定性波动明显，适合作为备选而非主站。

---

## 3. 横向对比总表

| 平台 | 免费额度（关键项） | 脚本化部署（无浏览器登录） | 自定义域名 + 免费 HTTPS | 大陆可达性（实测） | 每日更新可行 |
|---|---|---|---|---|---|
| **GitHub Pages** | 站点 ≤1 GB；100 GB/月软带宽；Actions 构建不计入 10/h 限额 | ✅ git push + `upload-pages-artifact`/`deploy-pages` | ✅ 自动签发 | ✅ **0.47 s 均**（20/20） | ✅ |
| **EdgeOne Makers** | 无限流量/请求；5 GB 存储；500 构建/月；200 自定义域名 | ✅ `edgeone makers deploy -t <token>`；官方 GH Actions | ✅ 但**需手动申请证书**；**大陆加速需 ICP** | ✅ **0.34–1.11 s** | ✅ |
| **Cloudflare Pages** | 500 构建/月；20,000 文件；25 MiB/文件；100 自定义域名/项目 | ✅ `wrangler pages deploy`（Token） | ✅ 自动签发 | ✅ **1.03 s 均**（20/20） | ✅ |
| **Netlify** | **300 credits/月硬上限**；部署 15 credits/次 | ✅ CLI + Deploy API | ✅ 自动签发 | ✅ **0.72 s 均**（20/20） | ❌ **450 credits > 300** |
| **Surge.sh** | 无限发布；1 个项目粒度 | ✅ `SURGE_TOKEN` + CLI/API（无 2FA） | ✅ 自动签发（免费） | ✅ **0.31–1.45 s** | ✅ |
| **Vercel** | 100 GB 传输；100 部署/天；**Hobby 禁止商用** | ✅ CLI/API | ✅ 自动签发 | ❌ `*.vercel.app` **DNS 污染**（6/6 000） | ⚠️ 仅绑自定义域名 |
| **GitLab Pages** | Free 档免费 | ✅ `.gitlab-ci.yml` | ✅ Let's Encrypt | ⚠️ `gitlab.io` 301/超时波动 | ⚠️ |
| **Codeberg Pages** | 免费；v2 对新用户已停用 | ✅ webhook / Forgejo Actions | ✅ 需 TXT 授权 + HTTP 首部署 | ✅ 2.30 s（6/6） | ✅ |
| **Render** | 静态站免费；同计 workspace 带宽 | ✅ Git push / API | ✅ Let's Encrypt + GTS 自动 | ⚠️ **3.87 s 均**（最慢） | ✅ |
| **Gitee Pages** | — | — | — | ❌ 域名 TCP 不通 | ❌ **已停服** |
| **Zenbur** | 免费档无托管算力 | — | — | — | ❌ 不适用 |
| **腾讯云 COS** | 50 GB 存储 × 180 天（**不含流量**） | ✅ | ✅ 需自行配证书 | ✅ 0.43 s | ❌ 流量费 |
| **阿里云 OSS** | 20 GB 存储 + 2 GB 流量 × 3 月 | ✅ | ✅ 需自行配证书 | ✅ 0.07–0.09 s | ❌ 流量费 |
| **Neocities** | 1 GB / 200 GB 带宽 | ✅ | ⚠️ 付费档更完整 | ❌ **RST 被墙** | ❌ |
| **SourceForge Pages** | 未取得官方数据 | 未知 | 未知 | ✅ 网络可达 | ❓ 信息缺口 |

---

## 4. GitHub 仓库能否用 GitHub Actions 自动全站部署？→ ✅ 可以，且是官方一等公民

**官方支持的两条路径**

**(A) 内置 Pages 构建（Jekyll / 静态文件直发）**
仓库 Settings → Pages → Source 选 `GitHub Actions`。

**(B) 自定义工作流（推荐，可完全控制构建过程）**
来源：<https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages>
```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v5
      - name: Build
        run: python build_json.py      # 你的本地 Python 逻辑可原样放进 runner
      - uses: actions/upload-pages-artifact@v4
        with:
          path: ./dist                 # 必须是目录；会被打成 gzip 单个 tar
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
    steps:
      - uses: actions/deploy-pages@v4
```
**硬约束（官方原文）**：
- artifact 必须是 **gzip 压缩的单个 tar**
- **必须 < 10 GB**
- **不得包含软链接或硬链接**
- `deploy-pages` 需 `needs` 指向 build job id，且需 environment（默认 `github-pages`）

**计费（官方原文）**：「**GitHub Actions usage is free for self-hosted runners and for public repositories that use standard GitHub-hosted runners**」→ **public 仓库完全免费**；Actions cache 独立 10 GB/repository 配额。

**关键优势**：用自定义 Actions 工作流发布，**不受 Pages「10 builds/hour」软上限约束**（官方明确说明该限制不适用于自定义工作流）。

**两种自动化范式的取舍**
| 范式 | 做法 | 优点 | 缺点 |
|---|---|---|---|
| **runner 内构建** | 每日定时 `schedule:` → runner 跑 Python 抓数据 → 构建 → 部署 | 全自动、机器无关 | 依赖 runner 能访问中国数据源（见 §5），且抓取失败会污染站点 |
| **本地构建 + push**（推荐） | 本地 Python 重建 JSON → `git push` → Actions 只做上传部署 | 数据抓取可控、可本地校验、失败不影响线上 | 需要本机每日执行一次 push（可用计划任务） |

→ **本项目推荐后者**：本地已具备 Python 环境与数据校验逻辑，push 到 GitHub 后由 Actions 完成发布，是风险最低的路径。

---

## 5. 中国数据源能否从美国 GitHub Actions runner 访问？

**前提事实**：官方文档说明「**Windows and Ubuntu runners are hosted in Azure** and subsequently have the same IP address ranges as the Azure datacenters. macOS runners are hosted in GitHub's own macOS cloud.」→ **标准 Ubuntu runner 位于 Azure（主要是美国区域）**，即「从美国出口访问中国网站」。

**实测方法（C 级证据）**：`check-host.net` 的美国（us1/us2/us3/us5）、加拿大（ca1）、日本（jp1）节点。

| 目标 | 节点 | 结果 |
|---|---|---|
| **`danjuanfunds.com/djapi/fund/detail/161725`** | ca1 / us1 / us2 / us5 | **全部 OK 200（0.57–0.81 s）**；jp1 亦 OK |
| **`www.csindex.com.cn`（主站）** | us3（Atlanta） | **OK 200 / 0.81 s** |
| **`www.csindex.com.cn/csindex-home/index-list/query-index-item`** | jp1 | **OK 200 / 2.33 s**（回显 `Date: Sat, 10 Oct 2026 11:45:16 GMT`） |
| **`fundgz.1234567.com.cn/js/161725.js`**（天天基金实时估值） | us1 / us3 / us5 | **全部 OK 200（0.94 / 1.82 / 1.21 s）** |
| **`api.fund.eastmoney.com/f10/lsjz?fundCode=161725`** | us1 / us5 | **全部 OK 200（0.61 / 1.46 s）** |
| `fund.eastmoney.com/pingzhongdata/161725.js` | us5 | OK 200 / 0.50 s |
| `fund.eastmoney.com`（主站首页） | us2 | OK 200 / 1.59 s，**但批量测试中 us2/us5 曾出现 `Connection reset by peer`**；ca1 亦 reset |
| `finance.sina.com.cn` | us1（洛杉矶） | **OK 200 / 0.82 s**（德/荷/塞尔维亚/俄/英/越节点亦全 OK；仅伊朗节点 reset） |
| `push2.eastmoney.com/api/qt/stock/get` | us5 / jp1 | **302 Found**（需跟随重定向） |

**结论**
1. ✅ **蛋卷基金（danjuanfunds.com）、中证指数（csindex.com.cn）、新浪财经（finance.sina.com.cn）、天天基金估值 API（fundgz.1234567.com.cn）、东方财富数据 API（api.fund.eastmoney.com）从美国均可无阻碍访问**，延迟 0.5–2.4 s，完全可支撑 GitHub Actions 每日构建。
2. ⚠️ **`fund.eastmoney.com` 主站首页有波动，出现过 `Connection reset by peer`** → 建议在 Actions 中对**页面抓取**（非 API）加**重试 + 超时 + 失败降级**（保留上一版 JSON 而不是发布空站点），或优先改用 `api.fund.eastmoney.com` / `fundgz.1234567.com.cn` 这类子域 API。
3. ⚠️ `push2.eastmoney.com` 返回 **302**，HTTP 客户端需开启 `follow redirects`。
4. **证据边界（必须声明）**：`check-host.net` 的节点不在中国大陆境内（其节点列表含 hk1 香港，无任何 `cn*`），因此本结论回答的是「**从美国等境外能否访问中国站点**」，这正是 GitHub Actions runner 的场景；它**不能**用来推断中国大陆用户的访问速度，后者由 §2 的本机上海移动实测承担。

---

## 6. 针对本项目的推荐方案与实操

### 6.1 站点画像与限额校验
- 总大小 **7.5 MB**，文件数 **~60**（含 ECharts vendor bundle ~1 MB）
- 校验：GitHub Pages 站点 ≤1 GB ✅；Cloudflare Pages 20,000 文件 / 25 MiB 单文件 ✅；EdgeOne 20,000 文件 / 25 MB 单文件 / 5 GB 总存储 ✅；**最大单文件约 1 MB（ECharts）远低于各平台上限** ✅

### 6.2 每日更新 × 各平台构建额度校验
| 平台 | 每月构建需求 | 免费额度 | 结论 |
|---|---|---|---|
| GitHub Pages | 30（Actions，public 仓库免费） | 无硬上限（自定义工作流不受 10/h 限制） | ✅ |
| Cloudflare Pages | 30 | 500/月 | ✅ |
| EdgeOne Makers | 30 | 500/月 | ✅ |
| Surge.sh | 30 | 无限发布 | ✅ |
| **Netlify** | 30 | **300 credits ÷ 15 = 20 次** | ❌ **第 20 天击穿** |

### 6.3 推荐组合

**方案 A（推荐给绝大多数情况）：GitHub Pages**
1. 站点仓库设为 **public**（Actions 免费、Pages 免费）
2. 本地 Python 脚本每日重建 JSON → `git push`
3. 仓库 Actions 用 `configure-pages@v5` + `upload-pages-artifact@v4` + `deploy-pages@v4` 自动发布
4. 绑自定义域名 + 勾选 Enforce HTTPS
5. **注意本机 hosts 劫持问题**：本机需修 hosts 或让脚本使用真实 IP，否则本地自测会失败

**方案 B（若速度是第一位，且手上域名已 ICP 备案）：EdgeOne Makers**
1. 加速区域选 **中国大陆可用区**（域名须先完成工信部备案）
2. 免费版：不限量流量/请求、5 GB 存储、500 构建/月、200 自定义域名
3. **务必执行**：在控制台为域名**手动申请免费 SSL 证书**（平台不会自动分配）
4. CI 部署：`npx edgeone makers deploy ./dist -n <project> -t $EDGEONE_API_TOKEN`
5. **若域名无备案**：必须选「全球可用区（不含中国大陆）」，此时大陆访问走境外节点，速度优势会打折扣

**方案 C（最省事的纯脚本发布）：Cloudflare Pages Direct Upload 或 Surge.sh**
- Cloudflare：`npx wrangler pages deploy ./dist --project-name=<p>` + API Token → **注意一旦选 Direct Upload 就无法再切回 Git 集成**
- Surge：`surge tokens add --domain <domain> -m ci` 铸造 Token → CI 中 `surge ./dist <domain>` 配 `SURGE_TOKEN`，**Token 永不触发 2FA**

### 6.4 明确不推荐
- **Netlify**（每日部署额度击穿）
- **Vercel**（`*.vercel.app` DNS 污染 + Hobby 禁商用）
- **Gitee Pages**（已停服）
- **Neocities**（大陆被墙）
- **Zeabur Free**（无免费托管算力）
- **腾讯云 COS / 阿里云 OSS**（下行流量必付、免费额度短期失效）
- **GitLab Pages / Render**（可用但实测稳定性/速度不足以做主力）

---

## 7. 数据缺口与不确定性声明

1. **SourceForge Pages**：官方文档被 Cloudflare 人机挑战拦截，**未能取得 2025-2026 官方证据**证明其仍作为免费静态托管存在 → 列为信息缺口，不作推荐。
2. **EdgeOne 免费版的 ICP 细节**：`custom-domain` 与 `domain-overview` 两处官方文档已明确「中国大陆可用区 / 全球可用区（含中国大陆）需工信部备案」，但**未找到官方对「免费版是否可选用中国大陆加速区域」的逐字说明**。现有最强书面证据为官方 banner「The World's First Free CDN with China Access」与配额页「流量防盗刷 **仅适用中国大陆地区**」。
3. **Surge.sh 强制 HTTPS 的付费归属**：定价页列为 Professional 功能，CLI/SSL 文档则写明免费可用方式 → **口径不一致，需实机验证**。
4. **中国大陆可达性均由单一测点（上海移动 183.195.101.95）实测**，未覆盖电信/联通/教育网等其它运营商。跨运营商表现可能不同。
5. **`check-host.net` 无中国大陆节点**，因此「大陆可达性」与「数据源从美国可达性」是两组独立证据，不可互相替代。
6. 本机 hosts 劫持导致所有涉及 `*.github.io / github.com` 的本地直连结果不可信，报告中相关结论均已用 `--resolve` 或真实 IP 校正。

---

## 8. 引用来源清单

**GitHub**
- <https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits>
- <https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages>
- <https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/about-custom-domains-and-github-pages>
- <https://docs.github.com/en/billing/concepts/product-billing/github-actions>
- <https://docs.github.com/en/actions/reference/runners/github-hosted-runners>

**Cloudflare**
- <https://developers.cloudflare.com/pages/platform/limits/>（Last updated Sep 5, 2026）
- <https://developers.cloudflare.com/pages/get-started/direct-upload/>（Last updated Apr 21, 2026）
- <https://developers.cloudflare.com/china-network/>（China Network，Enterprise + ICP）

**腾讯 EdgeOne**
- <https://pages.edgeone.ai/pricing>
- <https://pages.edgeone.ai/zh/document/limits-and-quotas>
- <https://pages.edgeone.ai/zh/document/custom-domain>
- <https://pages.edgeone.ai/zh/document/domain-overview>
- <https://pages.edgeone.ai/zh/document/configuring-an-https-certificate>
- <https://pages.edgeone.ai/zh/document/using-github-actions>
- <https://pages.edgeone.ai/zh/document/edgeone-cli>
- <https://pages.edgeone.ai/zh/document/faqs>
- <https://pages.edgeone.ai/llms.txt>

**Netlify**
- <https://www.netlify.com/pricing>
- <https://docs.netlify.com/api-and-cli-guides/cli-guides/get-started-with-cli/>

**Vercel**
- <https://vercel.com/docs/plans/hobby>
- <https://vercel.com/docs/limits>

**Surge.sh**
- <https://surge.sh/pricing>
- <https://surge.sh/docs/cli>
- <https://surge.sh/docs/cli/automation>
- <https://surge.sh/docs/cli/ssl>
- <https://surge.sh/docs/platform/custom-domains>
- <https://surge.sh/docs/api>

**Render**
- <https://render.com/docs/free>
- <https://render.com/docs/static-sites>

**腾讯云 COS**
- <https://cloud.tencent.com/document/product/436/6240>

**阿里云 OSS**
- <https://help.aliyun.com/zh/oss/product-overview/free-quota-for-new-users>

**GitLab Pages**
- <https://docs.gitlab.com/user/project/pages/>

**Codeberg Pages**
- <https://docs.codeberg.org/codeberg-pages/using-custom-domains/>

**Zeabur**
- <https://zeabur.com/pricing>

**Neocities**
- <https://neocities.org/supporter>
- <https://en.wikipedia.org/wiki/Neocities>

**Gitee（停服证据）**
- <https://help.gitee.com/sitemap.xml>（735 个 URL，无 pages 类目）
- <https://help.gitee.com/>（导航无 Pages）
- <https://help.gitee.com/repository/gitee-pages>（404）

---

*本报告为技术方案调研，非投资建议。所有免费额度与可达性数据为 2026-10-10 时点快照，厂商政策可能随时调整。*
