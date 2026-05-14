# Prefect Server：MySQL / OceanBase（MySQL 模式）后端接入说明

本文档汇总在本仓库中为 **OceanBase MySQL 兼容模式** 做 PoC 时的工作：在 **不改变 PostgreSQL / SQLite 既有行为** 的前提下，为 `mysql` 方言增加独立的数据库接口、基线迁移与运行期 SQL 兼容，并修复若干 **UPSERT / 索引 / 类型编译** 问题。

---

## 1. 目标与边界

| 项目 | 说明 |
|------|------|
| **目标** | Server 能连 MySQL 兼容库、完成基线迁移、支持基础 API / Worker / Deploy 路径（PoC 级）。 |
| **连接** | 异步驱动使用 **`mysql+asyncmy`**（需安装 `asyncmy`）。 |
| **迁移策略** | 独立的 Alembic 分支：`versions/mysql/`，首条迁移用 **ORM `MetaData` + `create_all`** 生成 schema，并在脚本内做 OceanBase 兼容改写（非复制 PG/SQLite 历史链）。 |
| **设计约束** | MySQL 专用逻辑放在 **MySQL 分支 / MySQL 迁移 / MySQL 查询组件**；**不**把 MySQL 实现挂在 SQLite QueryComponents 之上（除非明确设计）。 |

---

## 2. 架构：按方言注入三块

在 `provide_database_interface()` 中根据 SQLAlchemy 方言名 **`mysql`** 选择：

| 组件 | 类型 | 职责概要 |
|------|------|----------|
| `database_config` | `AsyncMySQLConfiguration` | 异步引擎、会话、`create_db`/`drop_db` 等（参考 PG，参数适配 MySQL，如超时）。 |
| `query_components` | `AsyncMySQLQueryComponents` | `insert` 使用 `mysql.insert`、JSON 构造/聚合、调度相关 SQL、worker 队列模板路径等。 |
| `orm` | `AsyncMySQLORMConfiguration` | `versions_dir` → `_migrations/versions/mysql`。 |

入口：`src/prefect/server/database/dependencies.py`。

---

## 3. 基线迁移（MySQL 专用）

**文件**：`src/prefect/server/database/_migrations/versions/mysql/2026_05_11_160000_3d1b2a5f0f1a_mysql_initial_schema.py`

在 `upgrade()` 中对 **`Base.metadata` 复制后的表** 做预处理，再 `metadata.create_all()`，主要包括：

1. **`Interval` + `server_default="0"`**  
   SQLAlchemy 在 MySQL 上映射为 `DATETIME`，`DEFAULT '0'` 非法（1067）。改为 **`DEFAULT '1970-01-01 00:00:00'`**，与 interval 演算使用的 epoch 语义一致（见 `server/utilities/database.py` 中 `MYSQL_EPOCH`）。

2. **JSON / TEXT / BLOB 上的 `server_default`**  
   OceanBase MySQL 模式限制：去掉这些类型上的默认值。

3. **唯一约束中的 TEXT/BLOB**  
   `UniqueConstraint` 无法使用 `mysql_length` 前缀，将参与唯一约束的 TEXT/BLOB 列收敛为 **`VARCHAR(255)`**（短 slug 等场景可接受；生产需按业务评估）。

4. **普通索引上的 TEXT/BLOB**  
   使用 **`Index(..., mysql_length=...)`** 生成 **前缀索引** `(col(255))`；含 `mysql_length` 时 MySQL DDL 编译器要求列为具名列，**不能**再用 `UnaryExpression(.desc())`，因此对这类索引 **用裸列顺序重建**（可能损失与 PG 完全一致的 **DESC** 索引语义，PoC 可接受）。

5. **JSON 列上的 GIN 类索引**  
   PG 的 `USING gin` 在 MySQL 上会变成对 JSON 的 BTREE，OceanBase 报错（如 3152）。**丢弃**仅含 JSON 表达式或 JSON 列上的该类索引（如 `events.related`）。

6. **`COALESCE(...) DESC` 等表达式索引**  
   OceanBase 不支持或语法不一致。**丢弃**非「纯列 / 列 ASC/DESC」的索引（如 `ix_flow_run__coalesce_start_time_*`）；保留 `start_time`、`expected_start_time` 等单列索引作为折中。

**降级**：`downgrade()` 使用 `reflect` + `drop_all`（PoC 级）。

---

## 4. SQL 编译与类型（`server/utilities/database.py`）

为 MySQL 方言增加的编译/适配示例：

- `now()` → **`CURRENT_TIMESTAMP`**（避免 `utc_timestamp()` 等在 OceanBase 上作默认值失败）。
- 无长度 **`String`** → **`TEXT`**（避免无界字符串被建成过短的 `VARCHAR(255)` 导致 **block_type.description** 等 1406）。
- **`GenerateUUID`** → **`(UUID())`** 等与 MySQL 兼容的写法。
- **日期/间隔函数**：`date_add` / `interval_add` / `date_diff` / `date_diff_seconds` 等使用 `timestampadd` / `timestampdiff` 等 MySQL 实现（与 PG/SQLite 分支并列）。

---

## 5. 查询与模板

- **`AsyncMySQLQueryComponents`**（`query_components.py`）：直接继承 `BaseQueryComponents`，实现 MySQL 下的 `insert`、`JSON` 相关、`make_timestamp_intervals`、flow run 图（v2 可用 **Python 拼装** 以降低方言差异）、worker 调度 SQL 等。
- **Jinja SQL**：`src/prefect/server/database/sql/mysql/get-runs-from-worker-queues.sql.jinja`（`GREATEST`、`ROW_NUMBER`、`JSON_UNQUOTE(JSON_EXTRACT(...))` 等）。

---

## 6. 事件与其它服务端路径

- **Events 写入**：MySQL 无 `RETURNING` 的兼容路径（如先查再插避免重复）；查询参数上限等按方言分支。
- **事件计数 / composite trigger** 等：对 MySQL 使用 `on_duplicate_key_update` 或等价逻辑（与 PG `on_conflict_do_update` 区分）。
- **API**：个别统计/列表查询增加 MySQL 分支（如 `next_runs_by_flow`、flow run 平均延迟等），使用 `timestampdiff` 等。

---

## 7. CRUD / UPSERT：MySQL 不使用 `on_conflict_*` 链式 API

PostgreSQL / SQLite 的 **`Insert.on_conflict_do_update` / `on_conflict_do_nothing`** 在 **`mysql.Insert`** 上**不存在**，必须在业务层按方言分支：

| 场景 | PostgreSQL / SQLite | MySQL |
|------|---------------------|--------|
| Upsert（更新） | `on_conflict_do_update(...)` | `on_duplicate_key_update(...)` |
| 插入忽略重复 | `on_conflict_do_nothing(...)` | `insert().prefix_with("IGNORE")` 或等价 |

已按此方式改动的示例（非穷尽，以代码为准）：

- `server/models/block_types.py`、`block_schemas.py`
- `server/models/workers.py`（`worker_heartbeat`）
- `server/models/flows.py`（`create_flow` → `INSERT IGNORE`）
- `server/models/deployments.py`（`create_deployment`、`FlowRun` 批量插入）

**后续**若新接口 500 且堆栈为 **`'Insert' object has no attribute 'on_conflict_...'`**，按上表在同一文件补 MySQL 分支即可。

---

## 8. 测试与本地命令

- **依赖与接口推断**：`tests/server/database/test_dependencies.py`（MySQL 配置/Query/ORM 推断）。
- **编译**：`tests/server/utilities/test_database.py`（如 `now()` 在 MySQL 下的编译）。
- **连接串示例**：`PREFECT_API_DATABASE_CONNECTION_URL=mysql+asyncmy://user:pass@host:3306/dbname?...`
- **Dry-run SQL**：`prefect server database upgrade --yes --dry-run` 可将 Alembic 生成的 SQL 重定向到文件审阅；**非**仓库必备产物。

---

## 9. 运维与环境提示（与迁移无关但常见）

- **监听地址**：默认 `127.0.0.1`，远端访问需 **`PREFECT_SERVER_API_HOST=0.0.0.0`** 并放行端口。
- **Worker 加载 Flow**：Deployment 若记录 **开发机绝对路径**（如 `/Users/...`），在 Linux Worker 上会 **`FileNotFoundError`**；应在 Worker 侧部署、使用 **Git/远程存储**，或统一工作目录策略。

---

## 10. 已知限制 / 后续工作（生产化前）

- MySQL 迁移链目前为 **单文件基线**，演进需后续 Alembic revision。
- 丢弃或弱化的索引（JSON GIN、coalesce、前缀/无 DESC）可能影响 **读性能**，需按业务压测与 DBA 规范优化。
- **`on_conflict_*`** 在其它 `server/models`、`events`、`services` 中可能仍有遗漏，需 **全库 grep** 与集成测试补齐。
- OceanBase 版本差异可能导致额外 DDL/SQL 限制，需以实际 errno/语法为准迭代。

---

*文档根据本分支 PoC 实施过程整理，具体行为以当前代码为准。*
