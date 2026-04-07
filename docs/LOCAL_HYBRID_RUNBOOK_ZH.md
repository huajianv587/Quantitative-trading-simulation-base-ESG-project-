# 本地长期开发 / 云端算力临时接入操作手册

说明：这份手册是给“将来重新接回远端 GPU / 5090”时使用的可选方案。
当前产品交付基线建议优先使用本地模式：`APP_MODE=local`、`LLM_BACKEND_MODE=auto`。

这套模式的目标很明确：

- 本地电脑是主工程、主数据、主开发环境
- 云端机器只负责 GPU 推理
- RAG、Qdrant、前后端、业务 API 都长期留在本地
- 将来如果本地换成 NVIDIA 机器，可以再把远端算力拔掉

## 一、职责划分

### 本地负责

- 代码开发与调试
- FastAPI 服务
- 前端页面
- RAG 检索
- Qdrant
- 原始 PDF / 索引 / docstore
- 测试、回归、接口验收

### 云端负责

- `Qwen2.5-7B + LoRA` 生成服务
- 纯算力工作

## 二、推荐运行模式

`.env` 中建议使用：

```env
APP_MODE=hybrid
LLM_BACKEND_MODE=remote
REMOTE_LLM_URL=http://127.0.0.1:8010
REMOTE_LLM_API_KEY=你的共享密钥
```

含义：

- `APP_MODE=hybrid`：本地为主，云端算力辅助
- `LLM_BACKEND_MODE=remote`：回答生成优先走远端 GPU 服务，失败后再走 DeepSeek，最后 OpenAI

## 三、第一次准备

### 1. 初始化本地 Python 环境

在项目根目录执行：

```bat
scripts\bootstrap_local_windows.bat
```

这个脚本会：

- 固定使用项目内 `.venv`
- 升级 `pip / setuptools / wheel`
- 安装本项目依赖

### 2. 准备云端模型服务

在云端项目目录执行：

```bash
cd /root/workspaces/esg-rag
source .venv-remote/bin/activate
export REMOTE_LLM_API_KEY=你的共享密钥
nohup python model-serving/remote_llm_server.py > remote-llm.log 2>&1 &
sleep 5
curl http://127.0.0.1:8010/health
```

健康返回示例：

```json
{"status":"ok","cuda":true,"adapter_path":"...","model_loaded":false}
```

`model_loaded=false` 是正常的，表示模型会在第一次真实请求时加载。

### 3. 打通本地到云端的 SSH 隧道

在本地新开一个终端窗口执行：

```bat
C:\Windows\System32\OpenSSH\ssh.exe -N -L 8010:127.0.0.1:8010 -p <云端端口> root@<云端地址>
```

这个窗口要一直保持打开。

本地验证：

```bat
curl http://127.0.0.1:8010/health
```

如果能返回健康 JSON，说明本地已经连通云端算力。

## 四、日常启动顺序

建议固定成下面这个顺序。

### 第 1 步：启动云端模型服务

如果云端没关机，先确认服务健康：

```bash
curl http://127.0.0.1:8010/health
```

如果没起来，再重新执行云端启动命令。

### 第 2 步：启动本地 SSH 隧道

```bat
C:\Windows\System32\OpenSSH\ssh.exe -N -L 8010:127.0.0.1:8010 -p <云端端口> root@<云端地址>
```

### 第 3 步：启动本地 Qdrant

```bat
scripts\start_local_qdrant_windows.bat
```

这个脚本会自动处理一个常见问题：

- 如果本机有一个错误启动的独立 `qdrant` 容器，它会先停掉
- 然后启动 `docker compose` 管理的 `qdrant`
- 确保本机 `6333` 端口真的可访问

### 第 4 步：启动本地主 API

```bat
scripts\run_local_hybrid_windows.bat
```

本质上它会以：

- `APP_MODE=hybrid`
- `LLM_BACKEND_MODE=remote`

来启动：

```bat
.venv\Scripts\python.exe -m uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload
```

### 第 5 步：做运行时体检

```bat
.venv\Scripts\python.exe scripts\runtime_doctor.py
```

理想结果：

- `qdrant.ok = true`
- `remote_llm.ok = true`
- `local_api.ok = true`

## 五、验证链路是否闭环

### 1. 健康检查

```bat
curl http://127.0.0.1:8000/health
```

### 2. 真实分析请求

```bat
python -c "import requests; r=requests.post('http://127.0.0.1:8000/agent/analyze', json={'session_id':'hybrid-test','question':'Please summarize DBS 2024 ESG priorities in 5 bullet points.'}, timeout=600); print(r.status_code); print(r.text)"
```

第一次请求可能会稍慢，因为云端模型会首次加载。

## 六、推荐日常工作流

### 做代码开发时

- 本地改代码
- 本地跑测试
- 本地跑 API
- 云端只提供生成算力

### 做检索/RAG优化时

- 在本地清洗语料
- 在本地重建或验证索引
- 在本地测试 `/agent/analyze`
- 不把 PDF、docstore、Qdrant 数据长期搬到云端

### 做最终上线验收时

- 再去云端做一次完整生产形态验证
- 再做 Docker 镜像收口

## 七、停止顺序

### 本地停止 API

在运行 `uvicorn` 的窗口按：

```text
Ctrl+C
```

### 本地停止 SSH 隧道

在 SSH 隧道窗口按：

```text
Ctrl+C
```

### 本地停止 Qdrant

```bat
docker compose stop qdrant
```

### 云端停止模型服务

先找进程：

```bash
ps -ef | grep remote_llm_server.py
```

再结束对应 PID。

## 八、常见问题

### 1. 本地 `curl http://127.0.0.1:8010/health` 不通

优先检查：

- 云端服务是不是还活着
- SSH 隧道窗口是不是被关了
- `.env` 里的 `REMOTE_LLM_URL` 是否仍指向 `http://127.0.0.1:8010`

### 2. 本地 `8000` 起不来

优先检查：

- 是否有旧的 Docker `app/nginx` 占用端口
- 是否误用了系统 Python，而不是 `.venv`
- 先执行：

```bat
.venv\Scripts\python.exe scripts\runtime_doctor.py
```

### 3. Qdrant 明明在 Docker Desktop 里，但本地连不上

通常是因为启动的是错误的独立容器，没有把 `6333` 暴露到宿主机。  
直接执行：

```bat
scripts\start_local_qdrant_windows.bat
```

### 4. 本地依赖安装异常

统一使用：

```bat
scripts\bootstrap_local_windows.bat
```

不要混用系统 Python、Windows Store Python、项目 `.venv`。

## 九、长期原则

这套工程的长期原则是：

- 本地是根
- 云端是可插拔算力
- 业务框架不依赖某一台云机器
- 算力后端以后可以替换，但主工程不要漂移

一句话总结：

**本地长期开发，云端临时借力；主工程留在本地，GPU 算力按需插拔。**
