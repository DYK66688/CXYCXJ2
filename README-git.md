# GitHub 版补充说明

这个仓库用于保存项目源码、配置结构和运行说明。

为了避免 GitHub 单文件/仓库体积限制，以及避免把本地敏感配置直接公开，以下内容没有上传到仓库：

- `models/`
  - 本地嵌入模型目录，当前项目实际使用的是 `models/bge-small-zh-v1.5/`
- `data/*.db`
  - 运行后生成的数据库文件，例如 `data/financial_formal.db`、`data/knowledge_formal.db`
- `config.json`
  - 本地路径和 API Key 配置
- 大体积 PDF 数据目录
  - `示例数据/附件2：财务报告/reports-上交所/`
  - `示例数据/附件2：财务报告/reports-深交所/`
  - `示例数据/附件5：研报数据/个股研报/`
  - `示例数据/附件5：研报数据/行业研报/`
  - `示例数据/正式数据/附件2：财务报告/reports-上交所/`
  - `示例数据/正式数据/附件2：财务报告/reports-深交所/`
  - `示例数据/正式数据/附件5：研报数据/个股研报/`
  - `示例数据/正式数据/附件5：研报数据/行业研报/`

## 给其他 Codex 的恢复方式

如果你是另一个 Codex，想把这个仓库拉下来后直接跑起来，按下面顺序处理。

### 1. 克隆仓库

```powershell
git clone https://github.com/DYK66688/CXYCXJ2.git
cd CXYCXJ2
```

### 2. 恢复缺失的大文件

从原始项目压缩包、原始比赛数据包或当前维护者本地目录中，把以下内容拷贝回仓库对应位置：

- `models/bge-small-zh-v1.5/`
- `示例数据/附件2：财务报告/reports-上交所/`
- `示例数据/附件2：财务报告/reports-深交所/`
- `示例数据/附件5：研报数据/个股研报/`
- `示例数据/附件5：研报数据/行业研报/`
- 如果使用正式数据，还需要：
  - `示例数据/正式数据/附件2：财务报告/reports-上交所/`
  - `示例数据/正式数据/附件2：财务报告/reports-深交所/`
  - `示例数据/正式数据/附件5：研报数据/个股研报/`
  - `示例数据/正式数据/附件5：研报数据/行业研报/`

说明：

- `附件1/附件3/附件4/附件6` 这些 Excel 文件如果仓库中已经存在，就不需要额外恢复。
- `data/*.db` 可以不恢复。如果没有数据库，重新运行 `task1` 和 `task3` 可以重建。

### 3. 补一个本地 `config.json`

仓库不包含 `config.json`，需要本地自行创建。

建议做法：

- 从原始项目目录复制一份 `config.json` 到仓库根目录。
- 然后至少确认以下字段：
  - `project_root`
  - `embedding.local_model_path`
  - `sample_data_path`
  - `db_path`
  - `knowledge_db_path`
  - `llm_configs[*].api_key`

如果当前要跑正式数据，推荐配置成：

- `sample_data_path`: `示例数据/正式数据`
- `db_path`: `data/financial_formal.db`
- `knowledge_db_path`: `data/knowledge_formal.db`

如果当前要跑示例数据，就改回：

- `sample_data_path`: `示例数据`
- 对应数据库路径改成示例库

### 4. Python 环境

推荐环境：

- Python `3.10`
- conda 环境名可以沿用 `taidibei`

安装依赖：

```powershell
conda create -n taidibei python=3.10 -y
conda activate taidibei
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

如果要处理扫描件 PDF，还要额外准备 OCR：

```powershell
pip install pytesseract
```

并安装 `tesseract-ocr` 本体。

### 5. 前端依赖

如果需要网页前端：

```powershell
cd frontend
npm install
cd ..
```

### 6. 运行顺序

如果数据库还没建：

```powershell
conda activate taidibei
python task1/run_task1.py
python task3/run_task3.py
```

如果数据库已经可用，直接运行：

```powershell
conda activate taidibei
python task2/run_task2.py
python -m backend.api.server
```

前端：

```powershell
conda activate taidibei
cd frontend
npm run dev
```

### 7. 常见判断

- `task1` 中如果日志提示“摘要且已检测到完整版，跳过入库”，这是正常行为。
- 如果 `task1` 中途被 `KeyboardInterrupt` 打断，数据库就是半成品，后面不要直接跑 `task2/task3`，应先完整重跑 `task1`。
- 如果图表、RAG 或问答异常，先检查大文件目录是否已经恢复完整，再检查 `config.json`。
