# 网易音乐人分享任务工具

网易音乐人分享任务自动分享工具，支持多用户、自动登录、每日签到、音乐人任务、动态分享、日志记录和 Bark 通知。

本仓库是面向 **Arcadia / NAS 定时任务** 的适配版本：程序每次运行会执行一次任务，然后退出，适合交给 Arcadia 按天定时触发。

## 致谢

本项目基于 [XingHehy/netease-musician-task](https://github.com/XingHehy/netease-musician-task/) 适配而来。感谢原作者 XingHehy 和原项目贡献者提供网易音乐人任务、Playwright 登录、Redis 状态管理、Docker 部署等核心能力。本仓库主要补充 Arcadia 运行入口、Bark 通知和更适合本地 NAS 部署的说明。

👉 **想快速了解能做什么？请查看功能预览：[`docs/PREVIEW.md`](./docs/PREVIEW.md)**

## Arcadia 部署

这个版本已经增加 Arcadia 入口，适合在 Arcadia 中按定时任务运行一次后退出，并通过 Bark 推送结果摘要。推荐流程是：安装依赖、配置 Redis、写入账号任务、在 Arcadia 中配置定时运行命令。

### 1. 安装依赖

在 Arcadia 运行环境或 NAS 终端进入项目目录后执行：

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

建议使用 Python 3.12。当前依赖中的 `ddddocr==1.5.6` 不支持 Python 3.13+，如果 Arcadia 默认 `python3` 是 3.13 或更高版本，请在 Arcadia 中把 Python 解释器切到 3.10-3.12，或通过 `PYTHON` 环境变量指定可用解释器后运行 `node arcadia.js`。

如使用 `LOGIN_METHOD=api` 可以不安装 Playwright 浏览器，但当前更推荐保留默认的 `playwright`。

### 2. 准备 Redis

程序使用 Redis 保存账号任务、Cookie、上次执行记录和 VIP 领取时间。Arcadia 环境中必须能访问你的 Redis。

在 Redis 中写入账号信息：

```bash
HSET netease:music:task task1 '{"phone": "your_phone", "password": "your_password"}'
```

说明：
- `netease:music:task` 是固定哈希表名。
- `task1` 是任务标识，多账号时可以写 `task2`、`account_a` 等不同 key。
- `phone` 和 `password` 是网易云账号登录信息，不要提交到 GitHub。
- 首次运行成功后，程序会把识别到的 `uid` 和登录 Cookie 写回 Redis。

### 3. 配置 Arcadia 环境变量

可以参考 `.env.example`，在 Arcadia 的环境变量中配置：

```bash
REDIS_URL=redis://your-redis-host:6379/5
LOGIN_METHOD=playwright
PLAYWRIGHT_PROFILE_BASEDIR=.playwright_profiles
PLAYWRIGHT_PROFILE_PER_USER=1
BARK=your-bark-key
ARC_RUN_MODE=all
ARC_BARK_ON_SUCCESS=1
```

#### 必填参数

| 参数 | 示例 | 说明 |
| --- | --- | --- |
| `REDIS_URL` | `redis://192.168.1.10:6379/5` | Redis 连接地址；如果有密码可写成 `redis://:password@host:6379/5` |
| `LOGIN_METHOD` | `playwright` | 建议固定为 `playwright`，网页登录更稳 |
| `BARK` | `your-bark-key` | Bark 推送 key；也可以填完整 Bark URL |

#### 推荐参数

| 参数 | 推荐值 | 说明 |
| --- | --- | --- |
| `PLAYWRIGHT_PROFILE_BASEDIR` | `.playwright_profiles` | 保存网页登录态，建议持久化这个目录 |
| `PLAYWRIGHT_PROFILE_PER_USER` | `1` | 多账号独立 profile，避免 Cookie 串号 |
| `EXECUTION_INTERVAL_DAYS` | `3` | 动态分享任务间隔天数 |
| `MAX_MONTHLY_SENDS` | `4` | 每月最多分享次数 |
| `ARC_RUN_MODE` | `all` | Arcadia 单次运行模式 |
| `ARC_BARK_ON_SUCCESS` | `1` | 成功时也推送 Bark；失败总会尝试推送 |
| `ARC_BARK_TITLE` | `网易音乐人任务` | Bark 标题前缀 |

`ARC_RUN_MODE` 可选值：
- `all`：默认，同时执行每日签到和动态分享检查。
- `daily`：只执行每日签到、音乐人签到等每日任务。
- `interval`：只执行动态分享、VIP 权益检查等间隔任务。

`BARK` 支持两种写法：
- 只填 Bark key：程序默认请求 `https://api.day.app/<key>`。
- 填完整地址：例如自建 Bark 服务地址。

未配置 `BARK` 时任务不会崩溃，只会跳过推送。

### 4. 在 Arcadia 中配置运行命令

优先使用 Python 入口：

```bash
python3 arcadia_run.py
```

如果 Arcadia 的脚本入口更适合 Node.js，也可以使用包装入口：

```bash
node arcadia.js
```

如果 Arcadia 默认 `python3` 不是 Python 3.10-3.12，可以在 Arcadia 里设置 `PYTHON` 环境变量，让 Node 包装入口调用指定解释器：

```bash
PYTHON=/path/to/python3.12
node arcadia.js
```

两个入口都会调用同一套任务逻辑。`arcadia_run.py` 会收集关键日志并在结束时通过 Bark 推送“成功/失败、耗时、关键结果摘要”；`arcadia.js` 只负责启动 Python，并在 Python 不可用时通过 Bark 发送启动失败通知。

### 5. 建议的 Arcadia 定时方式

建议每天运行 1 次，例如上午 9 点到 10 点之间。程序内部会根据 `EXECUTION_INTERVAL_DAYS` 和 `MAX_MONTHLY_SENDS` 判断是否真的执行动态分享，不满足条件时只会跳过分享并推送摘要。

如果你只想每天签到，不想发动态：

```bash
ARC_RUN_MODE=daily
```

如果你想把签到和动态分享拆成两个 Arcadia 任务：
- 任务 A：`ARC_RUN_MODE=daily`，每天早上运行。
- 任务 B：`ARC_RUN_MODE=interval`，每天稍晚运行。

### 6. 运行结果怎么看

运行后可以看：
- Bark 推送：本次状态、耗时、关键日志摘要。
- `log/netease_music.log`：核心业务日志。
- `log/netease_music_cron.log`：入口和任务调度相关日志。
- `debug/{手机号}/`：网页登录、滑块、二次验证失败时的截图。

## 快速开始

除 Arcadia 外，仍可使用 Docker 或直接 Python 运行。Docker 部署方式见下文 [Docker 部署](#docker-部署)。

## 最近更新 / 新功能概览

- **企业微信 Webhook 通知**：任务执行结果可推送到企业微信，实现异常告警与结果提醒
- **VIP 自动领取**：支持自动领取音乐人永久 VIP（自动完成任务后）
- **登录与分享增强**：
  - Playwright 网页端登录与分享，减少风控与安全验证异常
  - **自动更新cookie**：每次运行，会自动更新 Cookie
  - 支持复用网页 Cookie，降低 `301 用户未登陆`、分享异常概率
  - 登录流程支持易盾滑块（`ddddocr`）、网络风控文案识别；失败时可在项目根目录 `debug/{手机号}/` 查看截图
- **任务可靠性提升**：
  - 任务失败自动重试（最多多次尝试）以提高成功率
  - 统一配置文件 `config.py` 集中管理配置项，执行逻辑更加清晰可控

## 功能特性

- ✅ **每日签到任务**：自动执行网易云音乐日常签到，获取经验值
- ✅ **音乐人签到任务**：自动获取并完成音乐人云豆签到任务
- ✅ **自动分享音乐**：定时自动分享随机（避免风控）歌曲到动态
- ✅ **自动删除动态**：分享后约 10s 自动删除，避免打扰好友
- ✅ **多用户支持**：支持同时管理多个网易云音乐账号
- ✅ **智能登录**：优先使用缓存的 Cookie，失效后自动重新登录
- ✅ **任务分类执行**：每日任务每天执行，分享任务按间隔天数执行
- ✅ **执行记录管理**：Redis 存储执行记录，精确控制任务执行频率
- ✅ **环境变量配置**：支持通过环境变量灵活配置执行参数
- ✅ **日志管理**：详细的日志记录，支持日志轮转和大小限制
- ✅ **Docker 部署**：提供 Docker 镜像和 Compose 配置，便于部署
- ✅ **VIP 自动领取**：自动完成 VIP 相关权益的领取操作
- ✅ **企业微信通知**：通过企业微信 Webhook 推送任务执行结果和异常告警
- ✅ **任务失败重试机制**：任务失败时自动按策略重试，提高成功率
- ✅ **Playwright 支持**：基于 Playwright 的网页登录、音乐人任务与分享，降低接口风控风险

## 技术栈

- Python 3.12（推荐与 Docker 一致；最低建议 3.10+）
- Requests、PyCryptodome
- Redis（Cookie、任务数据、执行记录）
- APScheduler（定时调度）
- Playwright + Chromium（网页登录与部分页面能力）
- ddddocr（易盾滑块辅助识别）
- pyexecjs + Node.js（`checkToken.js`）
- Docker（可选）

## 依赖要求

- **Python**：建议 3.12，需安装 `requirements.txt`
- **Redis**：必须，用于任务与登录态
- **Node.js**：推荐安装；用于通过 `execjs` 执行 `checkToken.js` 生成 `checkToken`。若缺少可用的 JS 运行时，音乐人相关接口可能返回 `301 用户未登陆`。
- **Playwright 浏览器**：使用 `LOGIN_METHOD=playwright` 或运行 `playwright_handle/login.py` 前需执行：`python -m playwright install chromium`
- **Docker**（可选）：容器化部署

## 安装步骤

### 1. 克隆项目

```bash
git clone <repository-url>
cd netease-musician-task
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3.（推荐）安装 Playwright 浏览器
`API版基本上已无法使用 `

仅在需要网页登录 / `LOGIN_METHOD=playwright` 时需要：

```bash
python -m playwright install chromium
```

### 4. 配置 Redis

见下文 [环境变量说明](#环境变量说明)。通过 `REDIS_URL` 连接你的 Redis 实例。

### 5. 添加用户任务

在 Redis 的哈希表 `netease:music:task` 中为每个任务写入账号信息，例如：

```bash
HSET netease:music:task <task_key> '{"phone": "your_phone", "password": "your_password"}'
```

- `<task_key>`：任务唯一标识（自定义字符串）
- `phone`：网易云登录账号（手机号）
- `password`：密码（Playwright 与 API 登录均可能用到）

---

## 环境变量说明

配置集中在 `config.py`，以下为常用环境变量（默认值以代码为准）。

| 环境变量 | 说明 | 默认值 |
| --- | --- | --- |
| `REDIS_URL` | Redis 连接地址 | `redis://localhost:6379/5` |
| `SEND_TIME` | 每日调度触发时间（`HH:MM`） | `09:30` |
| `EXECUTION_INTERVAL_DAYS` | 分享类间隔任务的最小间隔天数 | `3` |
| `MAX_MONTHLY_SENDS` | 每月分享次数上限 | `4` |
| `LOGIN_METHOD` | 登录方式：`api`（接口） / `playwright`（网页 Cookie） | `playwright` |
| `PLAYWRIGHT_PROFILE_BASEDIR` | Playwright 用户数据目录（持久化登录态） | `.playwright_profiles` |
| `PLAYWRIGHT_PROFILE_PER_USER` | 是否按账号分子目录（建议 `1`，避免多账号串 Cookie） | `1` |
| `WECOM_WEBHOOK_KEY` | 企业微信机器人 Webhook 的 `key`，留空则不推送 | 空 |
| `BARK` | Arcadia Bark 推送 key 或完整推送地址，留空则不推送 | 空 |
| `BARK_SERVER` | Bark 服务地址，`BARK` 仅填 key 时使用 | `https://api.day.app` |
| `BARK_GROUP` | Bark 通知分组 | `网易音乐人任务` |
| `ARC_RUN_MODE` | Arcadia 单次任务模式：`all` / `daily` / `interval` | `all` |
| `ARC_BARK_ON_SUCCESS` | 成功时是否推送 Bark；失败总会尝试推送 | `1` |
| `ARC_BARK_TITLE` | Bark 通知标题前缀 | `网易音乐人任务` |

示例：

```bash
export REDIS_URL="redis://localhost:6379/5"
export SEND_TIME="09:30"
export EXECUTION_INTERVAL_DAYS="7"
export MAX_MONTHLY_SENDS="4"
export LOGIN_METHOD="playwright"  # 推荐：API版基本上已无法使用
export WECOM_WEBHOOK_KEY="your-wecom-webhook-key"
export BARK="your-bark-key"
export ARC_RUN_MODE="all"
```

---

## Playwright 网页登录说明

在接口登录易触发风控、或音乐人接口频繁 `301` 时，建议使用 **`LOGIN_METHOD=playwright`**，由浏览器完成登录并写入 Redis Cookie（约 7 天过期，失效后会自动再走登录流程）。

### 独立运行登录脚本（写入 Redis）

在项目**根目录**下执行（保证能正确找到 `core` 等模块；若从其他目录运行需配置 `PYTHONPATH`）：

```bash
python playwright_handle/login.py
```

按提示输入手机号与密码。脚本会：

1. 打开网易云登录页，自动完成「其他登录模式 → 协议 → 手机号登录 → 密码登录 → 输入账号密码 → 登录」等步骤
2. 如出现 **易盾滑块**，会尝试自动拖动；失败时日志会有 `[滑块]` 相关说明
3. 如出现 **「登录安全验证」**，会尝试生成「原设备扫码」类链接并打日志，部分步骤需人工在手机上完成
4. 若页面提示 **「您当前的网络环境存在安全风险」**，脚本会识别并终止，需更换网络 / 代理环境后再试
5. 登录失败、未触发验证码、滑块失败、二次验证超时等情况，会在项目根目录 **`debug/{手机号}/`** 下保存带时间戳的 PNG 截图，便于排查（各场景 `tag` 与日志关键字见 [docs/DEBUG_DOCS.md](./docs/DEBUG_DOCS.md)）。

登录成功后会尝试识别 `uid` 并将 Cookie 写入 Redis（键名形如 `netease:music:user:{uid}:cookie`）。

### 与主程序集成

`main.py` / `core.py` 在 `LOGIN_METHOD=playwright` 时会调用同一套 `browser_login` 逻辑；`PLAYWRIGHT_PROFILE_BASEDIR` 与 `PLAYWRIGHT_PROFILE_PER_USER` 控制浏览器用户数据目录，多账号务必保持 **每用户独立 profile**（默认已开启）。

---

## 使用方法

### 直接运行

在项目根目录：

```bash
python main.py
```

### 任务调度逻辑简述

1. **每日任务**（每天在 `SEND_TIME` 执行）：网易云日常签到、音乐人云豆签到等
2. **间隔任务**（每天在 `SEND_TIME` 延后约 5 分钟检测）：音乐人分享动态等；仅当距上次成功执行已满 `EXECUTION_INTERVAL_DAYS` 天且未超过 `MAX_MONTHLY_SENDS` 等限制时才会真正分享

执行记录与部分状态保存在 Redis 键 `netease:music:data` 等（详见下文）。

---

## 故障排查

| 现象 | 建议 |
| --- | --- |
| `301 用户未登陆` | 尝试 `LOGIN_METHOD=playwright`；确认 Node 可用、`checkToken.js` 正常；重新执行登录脚本或等待 Cookie 刷新 |
| 网页登录提示网络安全风险 | 更换 IP / 关闭可疑代理，稍后重试；查看 `debug/{手机号}/` 下截图 |
| 滑块反复失败 | 查看同目录截图与日志中的 `[滑块]`；确认本机网络可加载验证码图片 |
| Docker 内登录态丢失 | 检查是否挂载了 Playwright profile 目录，且 `PLAYWRIGHT_PROFILE_BASEDIR` 与挂载路径一致（见 [Docker 部署](#docker-部署)） |

---

## Docker 部署

### 使用预构建镜像（推荐）

可以直接使用已发布的 Docker 镜像，无需本地构建。镜像支持多架构（amd64/arm64），Docker 会自动选择适合你系统的版本：

```bash
docker pull xinghehy/netease-musician-task:latest
```

**支持的架构**：
- `linux/amd64` - 适用于 x86_64 处理器（Intel/AMD）
- `linux/arm64` - 适用于 ARM64 处理器（树莓派 4/5、Apple Silicon、ARM 服务器等）

### 构建镜像

如需自行构建：

```bash
docker build -t netease-musician-task:latest .
```

### Docker Compose

使用预构建镜像：

```bash
docker-compose up -d
```

或在 `docker-compose.yml` 中指定镜像：

```yaml
services:
  netease-musician-task:
    image: xinghehy/netease-musician-task:latest
    # ... 其他配置
```

默认 `docker-compose.yml` 将宿主机的 `./log`、`./playwright_profiles` 挂载到容器内。镜像工作目录为 `/app`，若使用默认 `PLAYWRIGHT_PROFILE_BASEDIR=.playwright_profiles`，数据在容器内**未**挂载到上述卷。为持久化浏览器登录态，建议在 Compose 中增加环境变量，使目录与卷一致，例如：

```yaml
# 推荐：API版基本上已无法使用
environment:
  - PLAYWRIGHT_PROFILE_BASEDIR=playwright_profiles
```

（与 `volumes` 里的 `/app/playwright_profiles` 对应。）

可选：挂载调试截图目录，便于宿主机查看：

```yaml
volumes:
  - ./debug:/app/debug
```

### docker run 示例

使用预构建镜像：

```bash
docker run -d --name netease-musician-task \
  -e TZ=Asia/Shanghai \
  -e REDIS_URL="redis://host.docker.internal:6379/0" \
  -e SEND_TIME="09:30" \
  -e EXECUTION_INTERVAL_DAYS="7" \
  -e MAX_MONTHLY_SENDS="5" \
  -e LOGIN_METHOD="playwright" \    # 推荐：API版基本上已无法使用
  -e PLAYWRIGHT_PROFILE_BASEDIR="playwright_profiles" \
  -e WECOM_WEBHOOK_KEY="your-wecom-webhook-key" \
  -v "$(pwd)/log:/app/log" \
  -v "$(pwd)/playwright_profiles:/app/playwright_profiles" \
  -v "$(pwd)/debug:/app/debug" \
  --restart always \
  xinghehy/netease-musician-task:latest
```

---

## 日志与本地目录

| 路径 | 说明 |
| --- | --- |
| `log/netease_music_cron.log` | 定时调度相关日志 |
| `log/netease_music.log` | 核心业务日志 |
| `debug/{手机号}/` | Playwright 登录失败等场景的页面截图（**项目根目录**，非 `playwright_handle` 下） |
| `.playwright_profiles/` | 默认 Playwright 用户数据目录（可通过 `PLAYWRIGHT_PROFILE_BASEDIR` 修改；建议加入 `.gitignore`） |

---

## Redis 键说明（摘要）

| 键 | 用途 |
| --- | --- |
| `netease:music:task` | 哈希表，`task_key` → 用户 JSON（含 `phone`、`password` 等） |
| `netease:music:data` | 任务执行间隔、上次执行时间等 |
| `netease:music:user:{uid}:cookie` | 用户登录 Cookie（带过期时间） |
| `netease:music:user:{uid}:userdata` | 用户资料缓存 |

---

## 项目结构

```
netease-musician-task/
├── main.py                 # 定时任务入口
├── arcadia_run.py          # Arcadia Python 单次运行入口
├── arcadia.js              # Arcadia Node 包装入口
├── arcadia_notify.py       # Bark 通知封装
├── core.py                 # 登录、任务、API 封装
├── config.py               # 环境变量与 Redis 初始化
├── checkToken.js           # checkToken 生成（需 Node/execjs）
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── playwright_handle/
│   ├── login.py            # Playwright 登录（滑块、二次验证、调试截图）
│   ├── musician.py         # 音乐人相关 Playwright 能力
│   └── friend.py           # 分享等 Playwright 能力
├── docs/
│   └── PREVIEW.md          # 功能预览
├── log/                    # 运行日志（自动创建）
├── debug/                  # 登录调试截图（按需生成）
└── README.md
```

---

## 注意事项

1. **Cookie 有效期**：网页登录写入的 Cookie 在 Redis 中约 7 天过期，失效后程序会尝试重新登录。
2. **网络环境**：需能访问网易云音乐相关域名；异常风控时优先检查 IP / 代理。
3. **账号安全**：密码存放在 Redis 任务数据中，请做好 Redis 访问控制与备份策略。
4. **工作目录**：建议在项目根目录运行 `python main.py`，以便日志、`debug`、`profile` 路径与预期一致。
5. **执行频率**：分享任务受 `EXECUTION_INTERVAL_DAYS` 与 `MAX_MONTHLY_SENDS` 共同约束，请合理设置避免风控。

---

## 许可证

MIT License

---

## 更新日志
- v1.4.3
  - 添加Cookie自动更新功能(每次执行任务后，更新最新的Cookie) -> 测试功能

- v1.4.2
  - 修复黑胶VIP自动领取功能(具体是否可用等下个月才能确认)

- v1.4.1
  - 增强网易云音乐登录调试能力（失败截图、风控识别等），详见 [docs/DEBUG_DOCS.md](./docs/DEBUG_DOCS.md)。

- v1.4.0
  - 添加企业微信 Webhook 通知功能

- v1.3.5
  - 优化 VIP 自动领取功能逻辑

- v1.3.4
  - 添加 VIP 自动领取功能支持

- v1.3.3
  - 优化 Docker 构建，提升构建效率和缓存利用率
  - 修改二次验证方式为原设备扫码验证，优化登录流程

- v1.3.2
  - Dockerfile 增加 Playwright 浏览器安装步骤

- v1.3.1
  - 添加 Playwright 获取音乐人任务方式，避免 `userMissionId` 获取失败

- v1.3.0
  - 添加 Playwright 登录、分享方式，避免出现「安全验证分享异常」
  - 添加任务执行失败重试机制，提高任务成功率

- v1.2.3
  - 新增任务执行失败重试机制，最多重试 3 次，提高任务成功率
  - 创建统一的配置文件 `config.py`，集中管理所有配置项
  - 修复预计下次执行时间计算逻辑，正确处理时间已过的情况
  - 修复分钟数溢出问题，正确处理跨小时的时间计算

- v1.2.0
  - 新增每日签到任务功能，自动执行网易云音乐日常签到
  - 新增音乐人签到任务功能，自动获取并完成音乐人云豆签到
  - 任务系统重构，分离每日任务和间隔执行的分享任务
  - 优化任务执行逻辑，提高任务稳定性和可靠性

- v1.1.0
  - 新增基于间隔天数的执行逻辑，每天定时检测
  - 添加执行记录存储功能
  - 优化环境变量配置，支持更多自定义参数
  - 完善日志记录和数据持久化

- v1.0.0
  - 初始版本
  - 支持多用户自动分享和删除动态
  - 支持定时任务和 Docker 部署
  - 实现日志管理和大小限制

## 友情链接
 - [LINUX DO 社区](https://linux.do)
 - [Docker Hub 镜像仓库](https://hub.docker.com/r/xinghehy/netease-musician-task)
