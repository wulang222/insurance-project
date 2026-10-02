# Insurance Agent Platform

Python Agent 服务的主入口是 `supervisor_agent`：它将请求分发给保险推荐、知识问答或 CRM 分析 Agent。正式 FastAPI 入口通过持久化 Harness 运行，并统一治理模型、工具与版本化 Prompt。

## 环境

- Python 3.13
- `uv`
- 通义千问 / DashScope 兼容接口
- MySQL：保险产品等结构化业务数据
- PostgreSQL：LangGraph Checkpoint 和长期 Store
- Milvus：唯一在线向量库

`chroma_data/` 是早期实验数据，不是在线运行依赖。

## 安装与配置

```bash
cd /Users/a1234/project/insurance-project/pythonProject
uv sync --all-groups
cp .env.example .env
```

按本地环境修改 `.env`，不要提交真实密钥。

## 启动

FastAPI 接口：

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 18084 --reload
```

LangGraph 开发服务：

```bash
uv run langgraph dev
```

旧 Java Portal 依赖的兼容接口为 `POST /chat` 和 `POST /chat/stream`。

持久化 Run API：

- `POST /v1/runs`：创建运行
- `GET /v1/runs/{run_id}`：查询状态
- `GET /v1/runs/{run_id}/events`：读取 SSE 事件
- `POST /v1/runs/{run_id}/resume`：使用原 `thread_id` 恢复中断

正式 FastAPI 入口必须配置 `POSTGRES_URI`。Checkpointer、Store、MySQL 和 Milvus 客户端均由 lifespan 创建和释放，不在模块导入阶段连接外部服务。

## 测试和静态检查

Day 1 验收命令：

```bash
uv run python -m pytest tests/contract tests/unit_tests -q
uv run python -m ruff check src tests
```

Day 2 持久化与恢复测试：

```bash
uv run python -m pytest tests/integration -q
```

Day 3 Gateway 与 Prompt Registry 验收：

```bash
uv run python -m pytest \
  tests/unit/test_tool_gateway.py \
  tests/unit/test_model_gateway.py \
  tests/unit/test_prompt_registry.py \
  tests/integration/test_tool_timeout_retry.py \
  tests/integration/test_tool_permission.py -q
```

正式业务链路必须从 FastAPI lifespan 注入 `ModelGateway`、`ToolGateway` 和
`PromptRegistry`。模块级 graph 仅保留给 LangGraph 本地开发与旧测试适配，不能作为
正式 HTTP 运行入口。Fake Repository 只能在测试或显式开发配置中创建。

Day 4 组合式家庭保障规划验收：

```bash
uv run python -m pytest \
  tests/contract/test_agent_registry.py \
  tests/integration/test_family_plan_graph.py \
  tests/integration/test_parallel_agents.py -q
```

包含“家庭保障/全家保险/家庭方案”等意图的请求会进入固定可解释计划：画像与
CRM 并行，保障缺口计算完成后产品查询与条款检索并行，最后聚合并执行合规检查。
保障缺口使用 `src/workflows/coverage_rules.json` 中的演示规则，不构成核保结论或
正式保险建议。

Day 5 Evidence RAG 与合规验收：

```bash
uv run python -m pytest \
  tests/security/test_prompt_injection.py \
  tests/security/test_unsupported_claims.py \
  tests/security/test_product_fabrication.py \
  tests/integration/test_compliance_revision.py -q
```

知识工具只返回带完整文档元数据的证据，不直接生成结论。家庭保障工作流按
`retrieve → rerank/deduplicate → evidence pack → answer` 执行；每条产品、规则或条款
事实必须指向产品库字段、规则版本或 Citation。输出先经过代码级事实校验，再经过
语义合规评估；失败时最多执行一次定向修订，第二次仍失败则返回人工复核兜底。

Contract 测试会 mock LLM、MySQL 和 Milvus，不依赖外部服务。需要显式运行供应商集成测试时，设置 `RUN_EXTERNAL_INTEGRATION_TESTS=true`。

## 目录入口

- `server.py`：FastAPI HTTP/SSE 入口
- `src/supervisor_agent/`：当前业务路由入口
- `src/insurance_agent/`：保险推荐
- `src/knowledge_agent/`：DB + Milvus 知识问答
- `src/crm_agent/`：CRM 分析
- `src/harness/`：统一运行类型、错误和依赖容器
- `src/middleware/`：模型与工具的超时、重试、预算、权限、脱敏和审计
- `src/tools/`：Pydantic 工具契约与显式 Repository 适配器
- `src/prompts/`：可版本化、可哈希、可回归的 Prompt Registry
- `src/agents/`：专业 Agent 的结构化输入输出契约
- `src/workflows/`：组合式家庭保障规划与配置化保障缺口规则
- `src/vectorizer/`：文档向量化到 Milvus

`simple_agent` 仅作为早期示例保留，不是项目主入口；`langchain-anthropic` 也仅由该示例使用。
