# SailCloth-01 · 帆布浸渍防水台

帆布间布卷与浸渍固化台账基线项目（Django 5 + DRF + Vue 3 SPA）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Django 5 · DRF · SimpleJWT · django-cors-headers · Gunicorn |
| 前端 | Vue 3 · Vite · Pinia · Vue Router |
| 数据库 | PostgreSQL 15 |
| 部署 | Docker Compose · Nginx（前端反代 `/api`） |

## 路径与端口

- **项目路径**：`d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01`
- **前端**：http://localhost:3740
- **API**：http://localhost:8740
- **PostgreSQL**：localhost:6140

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 管理员 |
| `worker` | `123456` | 操作工 |

登录页已预填 `admin` / `123456`。后端 entrypoint 执行 migrate + seed。

## 业务规则

布卷状态不可设为「已固化」（`cured`），除非该卷**最近一条** `DipRun` 的 `cureHours` 已记录且 **≥ 12**。

规则实现：`backend/core/rules.py`

## 快速启动

```bash
cd d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01
docker compose up --build
```

浏览器打开 http://localhost:3740

## SPA 信息架构

- **登录** → 进入主工作面
- **`/` 帆布间晾晒架（主）**：按帆布间挂布卷芯片（挂签状态 `raw` / `dipping` / `cured`）；点击打开右侧面板登记 `DipRun`、切换固化状态；架下为浸渍流水次要信息流
- **`/resin-total` 当日树脂加总台（只读）**：本间今天新登记浸渍的条数与树脂百分比合计（分间加总 + 当日明细），与晾晒架下方流水的今日记录加得上；不能改态、不能改树脂。顶栏与侧栏均可进入晾晒架与树脂加总
- **`/rolls` · `/dips`（次要台账）**：保留列表/表单 CRUD，侧栏降级为「台账」入口，非主路径

API 契约不变（JWT、`/api/lofts|rolls|dips|dashboard/`），新增只读 `GET /api/dips/daily-total/`。

## 并发去重

同一布卷同一浸渍日（`dip_date`，按本地时区从 `started_at` 派生）只许一笔 `DipRun` 入库：数据库唯一约束 `uniq_diprun_roll_dip_date` 兜底，并发重复登记返回 `409`，当日加总条数不会重复计数。

## 配色

海军蓝（navy）+ 帆布米色（canvas），与温室绿主题区分。
