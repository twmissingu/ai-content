# 部署指南

## 快速开始

### 环境要求

- Docker 20.10+ 和 Docker Compose 2.0+
- 或者：Python 3.14+、Node.js 20+

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入必要配置
```

必须配置的变量：

| 变量 | 说明 | 示例 |
|------|------|------|
| `LLM_BASE_URL` | LLM API 端点 | `https://api.xiaomimimo.com/v1` |
| `XIAOMI_API_KEY` | LLM API Key | `sk-xxx` |

可选变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_MODEL` | 模型名称 | `mimo-v2.5` |
| `FEISHU_WEBHOOK_URL` | 飞书告警 Webhook | - |
| `MONTHLY_BUDGET_USD` | 月度预算上限 | `15` |
| `CORS_ORIGINS` | 前端域名 | `http://localhost:5173` |
| `API_KEY` | API 认证密钥 | -（留空则不启用认证） |

### 2. Docker 部署（推荐）

```bash
# 构建并启动
docker compose up -d

# 查看日志
docker compose logs -f dashboard

# 停止服务
docker compose down
```

服务启动后：
- Dashboard API: `http://localhost:8710`
- 健康检查: `http://localhost:8710/api/health`

### 3. 本地开发部署

```bash
# 安装 Python 依赖
pip install -e .

# 启动后端
python3 dashboard/backend/main.py

# 新终端 - 启动前端
cd dashboard/frontend
npm install
npm run dev
```

- 前端: `http://localhost:5173`
- 后端: `http://localhost:8710`

---

## 生产环境配置

### 安全加固

1. **启用 API 认证**

   ```bash
   # .env
   API_KEY=your-strong-random-key-here
   ```

   客户端请求需携带 `X-API-Key` header。

2. **限制 CORS 来源**

   ```bash
   # 生产环境不要用 *
   CORS_ORIGINS=https://your-domain.com
   ```

3. **使用 HTTPS**

   在 Nginx/Caddy 反向代理后部署，配置 SSL 证书。

### Nginx 反向代理配置

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # 前端静态文件
    location / {
        root /path/to/dashboard/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8710;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket 代理
    location /ws {
        proxy_pass http://127.0.0.1:8710;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

### Caddy 反向代理配置

```
your-domain.com {
    root * /path/to/dashboard/frontend/dist
    file_server

    reverse_proxy /api/* localhost:8710
    reverse_proxy /ws localhost:8710 {
        header_up Connection {>Connection}
        header_up Upgrade {>Upgrade}
    }
}
```

---

## 数据持久化

Docker 部署时，以下目录通过 volume 挂载持久化：

| 容器路径 | 说明 |
|----------|------|
| `/app/data` | 数据库、日志、分析数据 |
| `/app/queue` | Agent 队列文件 |
| `/app/kb` | 知识库文件 |
| `/app/config` | 配置文件（提示词、审校模式等） |

**备份策略：**

```bash
# 备份数据目录
tar -czf gaoding-backup-$(date +%Y%m%d).tar.gz data/ queue/ kb/ config/
```

---

## 监控与告警

### 健康检查

```bash
curl http://localhost:8710/api/health
```

返回示例：

```json
{
  "status": "ok",
  "version": "0.7.0",
  "services": {
    "database": "ok",
    "search": {"status": "ok", "indexed_documents": 42}
  },
  "queue_sizes": {"pending": 5, "review": 2, "actions": 0, "failed": 0},
  "budget": {"current_cost": 3.5, "budget": 15.0, "percentage": 23.3},
  "disk": {"free_gb": 156.4, "percent_used": 66.0}
}
```

### 飞书告警

配置 `FEISHU_WEBHOOK_URL` 后，系统会在以下情况发送告警：
- 预算超限
- Agent 执行失败
- 磁盘空间不足

### Docker 健康检查

Docker Compose 内置健康检查，每 30 秒检测一次：

```bash
# 查看容器健康状态
docker inspect --format='{{.State.Health.Status}}' gaoding-dashboard
```

---

## 性能指标

基于本地测试的 API 响应时间：

| 端点 | 平均响应时间 | 吞吐量 |
|------|-------------|--------|
| `GET /api/health` | 2.1ms | 477 req/s |
| `GET /api/pipeline/status` | 1.1ms | 942 req/s |
| `GET /api/approval/queue` | 1.5ms | 673 req/s |
| `GET /api/topics` | 1.0ms | 965 req/s |
| `GET /api/config` | 1.2ms | 868 req/s |

速率限制：120 请求/分钟/IP。

---

## 故障排查

### 常见问题

**1. 前端无法连接后端**

检查 `VITE_API_BASE_URL` 环境变量是否指向正确的后端地址。

**2. LLM 调用失败**

```bash
# 测试 LLM 连通性
curl $LLM_BASE_URL/models -H "Authorization: Bearer $XIAOMI_API_KEY"
```

**3. 搜索索引异常**

```bash
# 重建搜索索引
curl -X POST http://localhost:8710/api/kb/reindex
```

**4. 队列堆积**

检查 `queue/actions/` 目录，确认 Agent 是否正常运行：

```bash
# 查看队列状态
curl http://localhost:8710/api/health | jq '.queue_sizes'
```

### 日志查看

```bash
# Docker 日志
docker compose logs -f dashboard --tail 100

# 本地日志文件
tail -f data/logs/gaoding.log
```

---

## 更新升级

```bash
# Docker 部署
git pull
docker compose build --no-cache
docker compose up -d

# 本地部署
git pull
pip install -e .
cd dashboard/frontend && npm install && npm run build
# 重启后端进程
```

---

## 架构图

```
┌─────────────────────────────────────────────┐
│                  Nginx/Caddy                │
│              (HTTPS + 反向代理)              │
└──────────┬────────────────┬─────────────────┘
           │                │
    ┌──────▼──────┐  ┌──────▼──────┐
    │  前端静态文件  │  │  FastAPI 后端  │
    │  (dist/)    │  │  (port 8710) │
    └─────────────┘  └──────┬──────┘
                            │
           ┌────────────────┼────────────────┐
           │                │                │
    ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
    │   SQLite DB  │  │  搜索索引    │  │  文件队列    │
    │  (analytics) │  │  (FTS5)    │  │  (queue/)   │
    └─────────────┘  └─────────────┘  └─────────────┘
```
