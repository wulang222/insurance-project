# Day 7 最终验证报告

- 验证日期：2026-10-03（Asia/Shanghai）
- Eval：55/55 通过，所有阈值达标
- Day 7 场景专项测试：21/21 通过

| 场景 | 自动化证据 | 结果 |
|---|---|---|
| A 完整家庭规划 | `test_family_plan_graph.py` | 路由、并行 Agent、产品、证据与汇总通过 |
| B 缺失信息并恢复 | `test_interrupt_resume.py`、`test_restart_recovery.py` | interrupt、resume 与重启恢复通过 |
| C 组合业务问题 | `test_family_plan_graph.py`、55 条 Eval | CRM、缺口、产品和知识组合通过 |
| D 依赖故障 | `test_dependency_failure.py`、`test_tool_timeout_retry.py`、`test_model_gateway.py` | 无 Mock 事实、读工具重试、模型降级通过 |
| E Prompt injection | `test_prompt_injection.py`、`test_compliance_revision.py` | 注入证据隔离，承诺性措辞被拦截 |

## 兼容与三端验证

- Python 旧 `/chat` 六字段结构 Contract：通过。
- Python 标准 SSE 阶段事件与 `run.result` Contract：通过。
- Java Portal 编译：通过。
- Java `ChatMessage.metadataJson` 新增测试：1/1 通过。
- Vue 生产构建：通过。

## 已知非本次失败

Java 全 Reactor 测试在 `insurance-common-core` 的两个历史 Bean 拷贝测试处失败：空包装类型复制到原始 `long` 会触发 `FatalBeanException`。该问题发生在 Portal 模块之前，与 Day 7 变更无关；本次使用指定测试方式验证新增 Java 行为。

模型型质量维度仍要求人工抽样，自动化报告不将其标记为机器自证。
