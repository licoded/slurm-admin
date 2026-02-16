# MySQL 数据库集成说明

## ✅ 已完成的功能

### 1. 数据库连接和初始化

已创建 `database.py` 模块，提供：
- **DatabaseConfig**: 从环境变量读取数据库配置
- **SlurmDatabase**: 数据库管理类，负责连接、表创建、数据操作
- **自动表创建**: 首次连接时自动创建必要的表结构

### 2. 数据库表结构

#### slurm_jobs 表
记录 Slurm 作业的基本信息和状态：
- job_id, job_name, script_path, command
- 资源分配：nodes, cpus, gpus, memory, partition_name
- 时间戳：submitted_at, started_at, completed_at
- 状态：status, exit_code

#### slurm_events 表
记录作业的所有生命周期事件：
- event_type: 事件类型（lifecycle, signal, error等）
- event_status: 事件状态（RUNNING, PAUSED, COMPLETED等）
- details: 事件详情
- metadata: JSON格式的额外信息

### 3. 集成到 SLM CLI

`slm.py` 现在支持：
- ✅ **自动数据库记录**：所有生命周期事件自动记录到数据库
- ✅ **slm submit**：提交作业时记录 SUBMITTED 状态
- ✅ **slm run**：监控运行时记录所有事件（RUNNING, PAUSED, RESUMED, COMPLETED, FAILED）
- ✅ **slm query**：查询数据库中的作业信息和事件历史
- ✅ **--no-db 选项**：可以禁用数据库记录
- ✅ **命令行参数**：可以覆盖数据库连接配置

### 4. 数据库配置

默认配置（在 `.env.example` 中）：
```bash
SLM_DB_HOST="licoded.site"
SLM_DB_PORT="3306"
SLM_DB_USER="slurm_admin_rw"
SLM_DB_PASSWORD="Slurm@Admin2026#RW"
SLM_DB_NAME="slurm_admin"
```

## 📊 使用示例

### 基本使用

```bash
# 1. 运行命令（自动记录到数据库）
uv run slm.py run -- python train.py --epochs 100

# 2. 查询作业信息
uv run slm.py query <job_id>

# 3. 查询事件历史
uv run slm.py query --events
```

### 查询脚本

```bash
# 查看最近的作业
uv run python scripts/query_jobs.py --recent 20

# 查看特定作业详情
uv run python scripts/query_jobs.py --job-id 12345

# 按状态查询
uv run python scripts/query_jobs.py --status FAILED

# 查看统计信息
uv run python scripts/query_jobs.py --stats
```

### 禁用数据库

```bash
# 临时禁用数据库记录
uv run slm.py --no-db run -- python script.py
```

## 🔧 已创建的文件

1. **database.py** - 数据库模块（连接、表创建、CRUD操作）
2. **sql/init_schema.sql** - 数据库初始化脚本
3. **scripts/query_jobs.py** - 查询脚本（支持多种查询方式）
4. **DATABASE_SETUP.md** - 数据库设置指南
5. 更新 **slm.py** - 集成数据库功能
6. 更新 **.env.example** - 添加数据库配置
7. 更新 **requirements.txt** 和 **pyproject.toml** - 添加 pymysql 依赖

## 🎯 核心特性

### 1. 自动记录
所有 SLM 命令自动记录事件，无需额外配置：
- SUBMITTED → 提交时
- RUNNING → 开始执行
- PAUSED → 收到 SIGTSTP
- RESUMED → 收到 SIGCONT
- TERMINATING → 收到 SIGTERM/SIGINT
- COMPLETED → 成功完成（exit code 0）
- FAILED → 失败完成（exit code != 0）

### 2. 信号感知
完全支持 Slurm 信号：
- `scontrol suspend <job_id>` → 记录 PAUSED
- `scontrol resume <job_id>` → 记录 RESUMED
- `scancel <job_id>` → 记录 TERMINATING

### 3. 灵活配置
三种配置方式（优先级从高到低）：
1. CLI 参数：`slm --db-host localhost ...`
2. 环境变量：`export SLM_DB_HOST="localhost"`
3. 默认值：在代码中定义

### 4. 查询能力
- 查询单个作业详情
- 查询作业事件历史
- 按状态过滤作业
- 统计分析（成功率、平均时长等）

## 🧪 测试结果

```bash
# 测试1：本地命令执行
$ uv run slm.py run -- echo "test"
[SLM.DB] Connected to MySQL at licoded.site:3306
[SLM.DB] Tables verified/created
[SLM.DB] Database logging enabled
test
[SLM] Starting command: echo test

# 测试2：查询记录
$ uv run python scripts/query_jobs.py --recent 5
Recent 5 Jobs:
--------------------------------------------------------------------------------
Job ID          | Name                      | Status       | Submitted
--------------------------------------------------------------------------------
N/A             | LocalTask                 | COMPLETED    | None
```

## 📝 注意事项

1. **partition 关键字问题**：
   - MySQL 中 `partition` 是保留关键字
   - 数据库列名使用 `partition_name`
   - 代码中通过别名处理兼容性

2. **本地测试**：
   - 本地运行时 `SLURM_JOB_ID` 为 "N/A"
   - 在 Slurm 环境中会自动使用真实的 Job ID

3. **数据库连接**：
   - 连接失败时会自动降级（禁用数据库功能）
   - 不会影响主要功能的执行

## 🚀 下一步

数据库集成已完成，可以：
1. 提交代码到 Git
2. 在 Slurm 集群上测试完整功能
3. 根据需要添加更多查询功能
4. 创建监控仪表板

## 📚 相关文档

- `DATABASE_SETUP.md` - 完整的数据库设置指南
- `README.md` - 主要文档
- `QUICKSTART.md` - 快速入门指南
