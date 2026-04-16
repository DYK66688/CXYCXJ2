# 上市公司财报"智能问数"助手

> 2026年泰迪杯数据挖掘挑战赛 B题 完整解决方案

## 项目简介

本项目是一个基于大语言模型（LLM）的上市公司财报智能问答系统，实现了从PDF财报自动解析、结构化数据库构建、自然语言查询、可视化分析到知识库增强的完整技术链路。

### 核心功能

- **任务一**：自动解析PDF财报 → 结构化SQLite数据库（4张财务表 + 自动校验）
- **任务二**：智能问数助手（自然语言→SQL→查询→图表→分析结论）
- **任务三**：增强助手（知识库检索 + 多意图规划 + 归因分析）
- **前端系统**：React + Ant Design 现代化对话界面

---

## （注意，当前项目仅供学习参考和二次开发，不代表任何最终结果和方案，切勿直接将项目直接作为竞赛结果提交）

## 快速开始

### 1. 环境准备

#### 创建Conda环境

```bash
# 创建Python 3.10环境
conda create -n taidibei python=3.10 -y
conda activate taidibei

# 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

#### 安装前端依赖

```bash
# npm的运行需要下载nodejs，如果电脑无法执行npm命令那请下载安装：https://nodejs.org/zh-cn/download
cd frontend
npm install
```

#### 下载嵌入模型（可跳过，任务三需要，当前models目录已下载有默认模型）

```bash
# 方式1：使用modelscope下载（推荐国内用户）
pip install modelscope
python -c "
from modelscope import snapshot_download
snapshot_download('AI-ModelScope/bge-small-zh-v1.5', cache_dir='./models')
"

# 方式2：使用HuggingFace下载
pip install huggingface_hub
python -c "
from huggingface_hub import snapshot_download
snapshot_download('BAAI/bge-small-zh-v1.5', local_dir='./models/bge-small-zh-v1.5')
"
```



#### API申请方式

| 平台     | 申请地址                      | 免费额度         | 推荐模型              |
| -------- | ----------------------------- | ---------------- | --------------------- |
| 硅基流动 | https://siliconflow.cn        | 注册送14元       | DeepSeek-V3, GLM-4-9B |
| 智谱清言 | https://open.bigmodel.cn      | GLM-4-Flash免费  | glm-4-flash           |
| DeepSeek | https://platform.deepseek.com | 注册送500万token | deepseek-chat         |

#### 替换方法

1. 注册对应平台账号
2. 创建API Key
3. 修改 `config.json` 中对应的 `api_key` 和 `base_url`
4. 设置 `enabled: true` 启用该配置

### 3. 配置项目路径（重要！）

本项目所有文件路径都统一由 `config.json` 中的 **`project_root`** 字段派生。首次使用或将项目拷贝到新机器时，**必须将其修改为您本地的实际项目根目录**。

打开 `config.json`，找到最顶部的 `project_root` 字段：

```json
{
  "project_root": "E:\\Projects2026\\taidibei2026-problemB",
  ...
}
```

**将其替换为您本地项目所在的绝对路径**，例如：

```json
// Windows 示例
"project_root": "D:\\Competition\\taidibei2026-problemB"

// macOS / Linux 示例
"project_root": "/home/username/taidibei2026-problemB"
```

> **说明**：`config.json` 中的 `db_path`、`knowledge_db_path`、`embedding.local_model_path` 等路径字段均使用**相对路径**（如 `data/financial.db`），系统会自动将它们拼接到 `project_root` 下解析为绝对路径。如果您不修改 `project_root`，系统会尝试通过代码位置自动推断，但**强烈建议手动确认该值正确**。

### 4. 运行任务（请严格按照流程运行！！）

#### 任务一：构建结构化财报数据库

```bash
conda activate taidibei
python task1/run_task1.py
```

执行后将：

- 解析所有PDF财报文件
- 提取结构化财务数据到SQLite数据库
- 执行自动校验
- 数据存储在 `data/financial.db`

#### 任务二：智能问数助手

```bash
python task2/run_task2.py
```

执行后将：

- 回答附件4中的所有问题
- 生成图表到 `results/` 目录
- 输出 `results/result_2.xlsx`

#### 任务三：增强智能问数助手

```bash
python task3/run_task3.py
```

执行后将：

- 构建研报知识库
- 回答附件6中的所有问题（含归因分析）
- 输出 `results/result_3.xlsx`

### 5. 启动前端系统

```bash
# 终端1：启动后端
python -m backend.api.server

# 终端2：启动前端
cd frontend
npm run dev
```

访问 http://localhost:3000 即可使用对话系统。

---

## 项目结构

```
taidibei2026-problemB/
├── backend/                    # 后端代码
│   ├── core/                   # 核心算法模块
│   │   ├── config.py           # 全局配置
│   │   ├── database.py         # SQLite数据库管理
│   │   ├── llm_client.py       # LLM API客户端
│   │   ├── embedding.py        # 嵌入模型
│   │   ├── pdf_parser.py       # PDF财报解析
│   │   ├── sql_generator.py    # NL→SQL生成
│   │   ├── visualizer.py       # 可视化图表
│   │   ├── knowledge_base.py   # 知识库管理
│   │   └── agent.py            # 智能问答Agent
│   └── api/                    # FastAPI接口
│       └── server.py           # API服务器
├── frontend/                   # React前端
│   ├── src/
│   │   ├── pages/              # 页面组件
│   │   ├── services/           # API和状态管理
│   │   └── App.tsx             # 主组件
│   └── package.json
├── task1/                      # 任务一脚本
│   └── run_task1.py
├── task2/                      # 任务二脚本
│   └── run_task2.py
├── task3/                      # 任务三脚本
│   └── run_task3.py
├── data/                       # 数据库存储
├── results/                    # 结果输出
├── models/                     # 本地模型
├── config.json                 # 运行时配置
└── requirements.txt            # Python依赖
```

---

## 嵌入模型替换方法

默认使用 `bge-small-zh-v1.5`（384维），如需替换：

1. 下载新模型到 `models/` 目录
2. 修改 `config.json` 中的 `embedding.local_model_path`
3. 更新 `embedding.dimension` 为新模型的维度

推荐模型：

- `BAAI/bge-small-zh-v1.5`（384维，轻量推荐）
- `BAAI/bge-base-zh-v1.5`（768维，更精确）
- `BAAI/bge-large-zh-v1.5`（1024维，最佳效果）

## 风格切换

如需切换前端UI风格，可以使用以下提示词与AI编程工具对话：

**切换为深色主题：**

> 请将frontend/src/App.tsx和index.css改为深色主题。ConfigProvider的theme token中colorBgContainer改为#1a1a2e，colorPrimary保持#1677ff，全局背景改为#16213e。调整所有Card和Sider的背景色为深色系。

**切换为企业级蓝色风格：**

> 请将前端改为专业的企业级蓝色风格。主色调改为#003366，辅助色#0066cc，背景色#f0f4f8。Header使用深蓝色渐变背景，Sider使用白色带阴影。

**切换为简约白色风格：**

> 请将前端改为极简白色风格。去除所有背景色渲变和阴影，使用纯白背景+细线边框。减少圆角，使用更小的字号和间距。

---

## 常见问题

### 环境配置问题

**Q1: LLM API调用失败？**

- **检查项1**：确认 `config.json` 中的API密钥是否正确
- **检查项2**：确认网络可以访问API地址（国内可能需要代理）
- **检查项3**：确认API账户余额充足
- **检查项4**：查看 `logs/` 目录下的错误日志
- **解决方案**：尝试切换其他LLM API（硅基流动、智谱清言等）

**Q2: 嵌入模型下载失败？**

- **国内用户**：使用modelscope下载（推荐）
  ```bash
  pip install modelscope
  python -c "from modelscope import snapshot_download; snapshot_download('AI-ModelScope/bge-small-zh-v1.5', cache_dir='./models')"
  ```
- **国外用户**：使用HuggingFace下载
- **手动下载**：从HuggingFace网站下载模型文件，放入 `models/bge-small-zh-v1.5/` 目录

**Q3: Conda环境创建失败？**

- **问题**：conda命令不存在
- **解决方案1**：安装Miniconda或Anaconda
- **解决方案2**：使用系统Python + venv

  ```bash
  python -m venv venv
  source venv/bin/activate  # Windows: venv\Scripts\activate
  pip install -r requirements.txt
  ```

**Q4: 前端依赖安装失败（npm install报错）？**

- **检查Node.js版本**：需要Node.js 16+，推荐18+
- **解决方法一：使用国内镜像**：
  ```bash
  npm config set registry https://registry.npmmirror.com
  npm install
  ```
- **解决方法二：如果还是不行**，可以下载npm的扩展包pnpm：[Node.js | pnpm下载安装与环境配置-CSDN博客](https://blog.csdn.net/yimeng_Sama/article/details/143824121)，验证好pnpm -v后，执行pnpm install即可
- **解决方法三：清除缓存**：
  ```bash
  rm -rf node_modules package-lock.json
  npm install
  ```

### 运行问题

**Q5: PDF解析结果不准确？**

- **原因1**：PDF是扫描件（图片），需要OCR

  - **解决方案**：安装 `pytesseract` 和 `tesseract-ocr`

  ```bash
  pip install pytesseract
  # Windows: 下载安装tesseract-ocr，配置环境变量
  ```
- **原因2**：PDF格式特殊，表格提取失败

  - **解决方案**：查看 `logs/task1.log` 日志，手动检查PDF文件
- **原因3**：文件名格式不符合预期

  - **解决方案**：确认PDF文件名符合上交所或深交所格式

**Q6: 数据库里没有数据？**

- **确认步骤1**：检查是否运行了 `python task1/run_task1.py`
- **确认步骤2**：检查 `data/financial.db` 文件是否存在
- **确认步骤3**：查看 `logs/task1.log` 是否有错误信息
- **确认步骤4**：检查PDF文件路径是否正确（默认 `示例数据/附件2：财务报告/`）

**Q7: SQL查询结果为空？**

- **检查SQL语句**：在数据库管理工具中手动执行SQL，确认语法正确
- **检查数据**：确认数据库中有对应时间范围和公司的数据
- **检查字段名**：确认使用的字段名与数据库Schema一致
- **查看日志**：检查 `logs/task2.log` 或 `logs/task3.log` 中的SQL执行记录

**Q8: 前端无法连接后端？**

- **确认后端运行**：访问 http://localhost:8000/docs 应该能看到API文档
- **确认端口**：后端默认8000端口，前端默认3000端口
- **检查代理配置**：前端 `vite.config.ts` 中的proxy配置是否正确
- **检查CORS**：确认后端CORS设置允许前端域名

**Q9: 任务执行很慢？**

- **原因1**：LLM API响应慢
  - **解决方案**：切换到更快的API（如GLM-4-Flash）
- **原因2**：PDF文件太多
  - **解决方案**：任务一支持批量处理，耐心等待或减少文件数量测试
- **原因3**：网络延迟
  - **解决方案**：使用国内API服务（硅基流动、智谱清言）

**Q10: 图表生成失败？**

- **检查matplotlib**：确认已安装matplotlib
- **检查中文字体**：如果图表中文乱码，需要配置中文字体
  ```python
  # 在 visualizer.py 中添加
  plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
  ```
- **检查数据格式**：确认查询结果数据格式正确

### 数据问题

**Q11: 数据校验失败？**

- **查看校验报告**：检查 `logs/validation_report.txt`
- **常见问题**：
  - 利润表不平衡：可能是数据提取错误，检查PDF源文件
  - 资产负债表不平衡：检查总资产、总负债、股东权益字段
  - 比率异常：检查计算逻辑和数据单位

**Q12: 知识库检索结果不相关？**

- **调整相似度阈值**：在 `knowledge_base.py` 中调整 `min_score` 参数
- **优化分块策略**：调整 `chunk_size` 和 `chunk_overlap` 参数
- **更换嵌入模型**：使用更大的模型（bge-base-zh-v1.5 或 bge-large-zh-v1.5）

**Q13: 多轮对话上下文丢失？**

- **检查session_id**：确认前端正确传递session_id
- **检查数据库**：确认对话历史正确保存到数据库
- **查看日志**：检查agent.py中的会话管理逻辑

### 结果提交问题

**Q14: 生成的Excel文件格式不对？**

- **检查字段**：确认Excel包含Q（问题）和A（回答）列
- **检查图片路径**：确认图片路径正确，图片文件存在
- **检查JSON格式**：如果A列是JSON，确认格式符合要求

**Q15: 结果文件在哪里？**

- **任务二结果**：`results/result_2.xlsx`
- **任务三结果**：`results/result_3.xlsx`
- **图表文件**：`results/` 目录下的 `.jpg` 文件

---

## 优化建议与二次开发指南

本项目提供了一个**完整的基线解决方案**，您可以在其基础上进行深度优化和二次开发，以提升性能和准确率。以下是详细的优化方向和可执行步骤。

### 🎯 优化方向概览

| 优化方向       | 预期提升 | 难度 | 优先级 |
| -------------- | -------- | ---- | ------ |
| PDF解析准确率  | +10-20%  | 中   | ⭐⭐⭐ |
| SQL生成准确率  | +15-25%  | 中高 | ⭐⭐⭐ |
| 知识库检索精度 | +20-30%  | 中   | ⭐⭐   |
| 响应速度       | +50-100% | 低中 | ⭐⭐   |
| 成本优化       | -30-50%  | 低   | ⭐⭐⭐ |

---

### 1. PDF解析优化

#### 1.1 增强规则提取（预期提升：+10-15%准确率）

**优化思路**：当前规则提取主要依赖关键词匹配，可以增加更多规则模式。

**可执行步骤**：

```python
# 文件：backend/core/pdf_parser.py

# Step 1: 添加更多财务指标的正则模式
FINANCIAL_PATTERNS = {
    'total_operating_revenue': [
        r'营业总收入[：:]\s*([\d,，]+\.?\d*)',  # 现有
        r'营业收入合计[：:]\s*([\d,，]+\.?\d*)',  # 新增
        r'主营业务收入[：:]\s*([\d,，]+\.?\d*)',  # 新增
    ],
    'net_profit': [
        r'净利润[：:]\s*([\d,，]+\.?\d*)',  # 现有
        r'归属于.*净利润[：:]\s*([\d,，]+\.?\d*)',  # 新增
        r'净利润.*?([\d,，]+\.?\d*)\s*万元',  # 新增
    ],
    # ... 为每个字段添加3-5个变体模式
}

# Step 2: 实现多模式匹配函数
def extract_with_multiple_patterns(text: str, patterns: List[str]) -> Optional[float]:
    """尝试多个模式，返回第一个匹配结果"""
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return parse_number(match.group(1))
    return None

# Step 3: 在 extract_financial_data_by_rules 中使用
def extract_financial_data_by_rules(text, tables, meta):
    data = {}
    for field_name, patterns in FINANCIAL_PATTERNS.items():
        # 先在表格中查找
        value = search_in_tables(tables, patterns)
        if not value:
            # 再在文本中查找
            value = extract_with_multiple_patterns(text, patterns)
        data[field_name] = value
    return data
```

**预期效果**：规则提取完整度从70%提升到85%+，减少LLM调用成本。

#### 1.2 表格结构识别优化（预期提升：+5-10%准确率）

**优化思路**：使用更智能的表格识别算法，识别合并单元格、跨页表格等。

**可执行步骤**：

```python
# Step 1: 安装依赖
# pip install camelot-py[cv] tabula-py

# Step 2: 添加多种表格提取方法
def extract_tables_advanced(pdf_path: str) -> List[Dict]:
    """使用多种方法提取表格，取最优结果"""
    methods = []
  
    # 方法1：pdfplumber（现有）
    methods.append(('pdfplumber', extract_with_pdfplumber(pdf_path)))
  
    # 方法2：camelot（适合结构化表格）
    try:
        import camelot
        tables = camelot.read_pdf(pdf_path, pages='all')
        methods.append(('camelot', [t.df.to_dict() for t in tables]))
    except:
        pass
  
    # 方法3：tabula（适合复杂表格）
    try:
        import tabula
        tables = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True)
        methods.append(('tabula', tables))
    except:
        pass
  
    # 选择最完整的方法
    return select_best_method(methods)

# Step 3: 实现表格质量评分
def score_table_quality(table: Dict) -> float:
    """评估表格质量（行数、列数、数据完整性）"""
    score = 0
    if len(table.get('rows', [])) > 5:
        score += 0.3
    if has_financial_keywords(table):
        score += 0.4
    if has_numeric_data(table):
        score += 0.3
    return score
```

#### 1.3 OCR增强（针对扫描件PDF）

**可执行步骤**：

```python
# Step 1: 安装OCR依赖
# pip install pytesseract pdf2image pillow
# Windows: 下载安装 tesseract-ocr

# Step 2: 添加OCR检测和提取
def extract_with_ocr(pdf_path: str) -> str:
    """对扫描件PDF使用OCR提取文本"""
    from pdf2image import convert_from_path
    import pytesseract
  
    images = convert_from_path(pdf_path)
    text = ""
    for img in images:
        text += pytesseract.image_to_string(img, lang='chi_sim+eng')
    return text

# Step 3: 在解析流程中添加OCR分支
def parse_pdf(pdf_path: str):
    # 检测是否为扫描件
    if is_scanned_pdf(pdf_path):
        text = extract_with_ocr(pdf_path)
    else:
        text = extract_text_from_pdf(pdf_path)
    # ... 后续处理
```

---

### 2. SQL生成优化

#### 2.1 Few-Shot Learning（预期提升：+10-15%准确率）

**优化思路**：在Prompt中添加更多示例，让LLM学习正确的SQL生成模式。

**可执行步骤**：

```python
# 文件：backend/core/sql_generator.py

# Step 1: 添加Few-Shot示例库
FEW_SHOT_EXAMPLES = [
    {
        "question": "2024年华润三九的净利润是多少？",
        "sql": "SELECT net_profit FROM income_sheet WHERE stock_abbr='华润三九' AND report_period='2024FY'",
        "explanation": "单公司单指标查询，使用WHERE条件过滤"
    },
    {
        "question": "近三年净利润最高的top5企业是哪些？",
        "sql": "SELECT stock_abbr, net_profit FROM income_sheet WHERE report_period LIKE '%FY' AND report_year >= 2022 GROUP BY stock_abbr ORDER BY net_profit DESC LIMIT 5",
        "explanation": "排名查询，使用GROUP BY和ORDER BY，注意时间范围"
    },
    # ... 添加20-30个典型示例
]

# Step 2: 根据问题类型选择相关示例
def select_relevant_examples(question: str, intent: Dict, num_examples: int = 5) -> List[Dict]:
    """选择与当前问题最相关的示例"""
    # 根据意图类型匹配
    relevant = [ex for ex in FEW_SHOT_EXAMPLES if ex['intent_type'] == intent['type']]
    # 根据关键词相似度排序
    relevant.sort(key=lambda x: calculate_similarity(question, x['question']), reverse=True)
    return relevant[:num_examples]

# Step 3: 在generate_sql中插入示例
async def generate_sql(question, intent, history):
    examples = select_relevant_examples(question, intent)
    prompt = f"""
    ## 示例（参考这些示例生成SQL）
    {format_examples(examples)}
  
    ## 当前问题
    {question}
    ...
    """
```

#### 2.2 SQL后处理与验证（预期提升：+5-10%准确率）

**优化思路**：生成SQL后，进行语法检查、语义验证、结果预览。

**可执行步骤**：

```python
# Step 1: 添加SQL语法检查
def validate_sql_syntax(sql: str) -> Tuple[bool, str]:
    """检查SQL语法"""
    # 使用sqlparse库
    import sqlparse
    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            return False, "SQL解析失败"
        # 检查是否包含危险操作
        if any(keyword in sql.upper() for keyword in ['DROP', 'DELETE', 'UPDATE', 'ALTER']):
            return False, "包含危险操作"
        return True, ""
    except Exception as e:
        return False, str(e)

# Step 2: 添加SQL语义验证
def validate_sql_semantics(sql: str, schema: Dict) -> Tuple[bool, str]:
    """验证SQL中的表名和字段名是否存在"""
    # 提取表名和字段名
    tables = extract_table_names(sql)
    fields = extract_field_names(sql)
  
    # 检查表名
    for table in tables:
        if table not in schema:
            return False, f"表 {table} 不存在"
  
    # 检查字段名
    for table, field in fields:
        if field not in schema[table]['fields']:
            return False, f"字段 {table}.{field} 不存在"
  
    return True, ""

# Step 3: 添加结果预览（Dry Run）
async def preview_sql_result(sql: str, limit: int = 5) -> Dict:
    """预览SQL执行结果（限制返回行数）"""
    preview_sql = f"SELECT * FROM ({sql}) LIMIT {limit}"
    try:
        result = db.execute(preview_sql)
        return {"success": True, "row_count": len(result), "sample": result[:3]}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Step 4: 在generate_sql中集成验证
async def generate_sql_with_validation(question, intent, history):
    max_retries = 3
    for i in range(max_retries):
        sql = await generate_sql(question, intent, history)
  
        # 语法检查
        valid, error = validate_sql_syntax(sql)
        if not valid:
            # 让LLM修复
            sql = await fix_sql_with_llm(sql, error, question)
            continue
  
        # 语义验证
        valid, error = validate_sql_semantics(sql, DB_SCHEMA)
        if not valid:
            sql = await fix_sql_with_llm(sql, error, question)
            continue
  
        # 预览结果
        preview = await preview_sql_result(sql)
        if preview['success'] and preview['row_count'] > 0:
            return sql
        elif preview['row_count'] == 0:
            # 结果为空，可能需要调整查询条件
            sql = await adjust_sql_for_empty_result(sql, question)
  
    return sql
```

#### 2.3 上下文增强（预期提升：+5%准确率）

**优化思路**：在SQL生成时，提供更多上下文信息（数据库统计信息、示例数据等）。

**可执行步骤**：

```python
# Step 1: 添加数据库统计信息收集
def get_database_statistics(db: DatabaseManager) -> Dict:
    """收集数据库统计信息"""
    stats = {
        'tables': {},
        'sample_data': {}
    }
  
    for table in ['core_performance_indicators_sheet', 'income_sheet', ...]:
        # 获取表行数
        count = db.get_table_row_count(table)
        stats['tables'][table] = {'row_count': count}
  
        # 获取示例数据
        sample = db.execute(f"SELECT * FROM {table} LIMIT 3")
        stats['sample_data'][table] = sample
  
        # 获取时间范围
        time_range = db.execute(f"SELECT MIN(report_period), MAX(report_period) FROM {table}")
        stats['tables'][table]['time_range'] = time_range
  
    return stats

# Step 2: 在SQL生成Prompt中包含统计信息
async def generate_sql(question, intent, history):
    stats = get_database_statistics(self.db)
    prompt = f"""
    ## 数据库统计信息
    {format_statistics(stats)}
  
    ## 示例数据
    {format_sample_data(stats['sample_data'])}
  
    ## 用户问题
    {question}
    ...
    """
```

---

### 3. 知识库检索优化

#### 3.1 混合检索（Hybrid Search）（预期提升：+15-20%准确率）

**优化思路**：结合向量检索和关键词检索，提升检索精度。

**可执行步骤**：

```python
# 文件：backend/core/knowledge_base.py

# Step 1: 添加关键词检索
def keyword_search(query: str, top_k: int = 10) -> List[Dict]:
    """基于关键词的BM25检索"""
    # 使用rank_bm25库
    from rank_bm25 import BM25Okapi
  
    # 对查询和文档进行分词
    query_terms = jieba.cut(query)
    doc_terms = [jieba.cut(chunk['content']) for chunk in self._chunks_cache]
  
    # 构建BM25索引
    bm25 = BM25Okapi(doc_terms)
  
    # 检索
    scores = bm25.get_scores(query_terms)
    top_indices = np.argsort(scores)[::-1][:top_k]
  
    results = []
    for idx in top_indices:
        results.append({
            **self._chunks_cache[idx],
            'keyword_score': float(scores[idx])
        })
    return results

# Step 2: 实现混合检索
def hybrid_search(self, query: str, top_k: int = 5, alpha: float = 0.7) -> List[Dict]:
    """
    混合检索：向量检索 + 关键词检索
    alpha: 向量检索权重（0-1）
    """
    # 向量检索
    vector_results = self.search(query, top_k=top_k * 2)
  
    # 关键词检索
    keyword_results = self.keyword_search(query, top_k=top_k * 2)
  
    # 合并结果（按文档ID去重）
    merged = {}
    for result in vector_results:
        doc_id = result['source_path'] + str(result['chunk_index'])
        merged[doc_id] = {
            **result,
            'vector_score': result['score'],
            'keyword_score': 0
        }
  
    for result in keyword_results:
        doc_id = result['source_path'] + str(result['chunk_index'])
        if doc_id in merged:
            merged[doc_id]['keyword_score'] = result['keyword_score']
        else:
            merged[doc_id] = {
                **result,
                'vector_score': 0,
                'keyword_score': result['keyword_score']
            }
  
    # 计算综合得分
    for doc_id, result in merged.items():
        result['final_score'] = (
            alpha * result['vector_score'] + 
            (1 - alpha) * result['keyword_score']
        )
  
    # 排序返回
    sorted_results = sorted(merged.values(), key=lambda x: x['final_score'], reverse=True)
    return sorted_results[:top_k]
```

#### 3.2 重排序（Reranking）（预期提升：+10-15%准确率）

**优化思路**：使用更强大的重排序模型对检索结果重新排序。

**可执行步骤**：

```python
# Step 1: 安装重排序模型
# pip install torch sentence-transformers
# 使用bge-reranker模型

# Step 2: 添加重排序模块
class Reranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(model_name)
  
    def rerank(self, query: str, candidates: List[Dict]) -> List[Dict]:
        """对候选结果重排序"""
        pairs = [[query, cand['content']] for cand in candidates]
        scores = self.model.predict(pairs)
  
        # 更新得分并排序
        for i, cand in enumerate(candidates):
            cand['rerank_score'] = float(scores[i])
  
        candidates.sort(key=lambda x: x['rerank_score'], reverse=True)
        return candidates

# Step 3: 在知识库检索中集成
def search_with_rerank(self, query: str, top_k: int = 5):
    # 先检索更多候选（top_k * 3）
    candidates = self.hybrid_search(query, top_k=top_k * 3)
  
    # 重排序
    reranker = Reranker()
    reranked = reranker.rerank(query, candidates)
  
    return reranked[:top_k]
```

#### 3.3 查询扩展（Query Expansion）（预期提升：+5-10%准确率）

**优化思路**：使用LLM扩展用户查询，添加同义词和相关术语。

**可执行步骤**：

```python
# Step 1: 实现查询扩展
async def expand_query(query: str, llm: LLMClient) -> str:
    """使用LLM扩展查询"""
    prompt = f"""
    用户问题：{query}
  
    请生成3-5个相关的查询变体，包括：
    1. 同义词替换
    2. 相关术语补充
    3. 上下文信息
  
    输出格式：每行一个查询变体
    """
  
    expanded = await llm.chat(prompt)
    queries = [query] + expanded.strip().split('\n')
    return queries

# Step 2: 多查询检索
def multi_query_search(self, queries: List[str], top_k: int = 5) -> List[Dict]:
    """对多个查询分别检索，然后合并结果"""
    all_results = {}
  
    for query in queries:
        results = self.search(query, top_k=top_k)
        for result in results:
            doc_id = result['source_path'] + str(result['chunk_index'])
            if doc_id not in all_results:
                all_results[doc_id] = result
            else:
                # 取最高分
                all_results[doc_id]['score'] = max(
                    all_results[doc_id]['score'],
                    result['score']
                )
  
    sorted_results = sorted(all_results.values(), key=lambda x: x['score'], reverse=True)
    return sorted_results[:top_k]
```

---

### 4. 性能优化

#### 4.1 缓存优化（预期提升：+50-100%响应速度）

**可执行步骤**：

```python
# Step 1: 添加Redis缓存（可选）
# pip install redis

import redis
import json
import hashlib

class CacheManager:
    def __init__(self):
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
        self.local_cache = {}  # 本地内存缓存
  
    def get_cache_key(self, query: str, context: str = "") -> str:
        """生成缓存键"""
        content = query + context
        return hashlib.md5(content.encode()).hexdigest()
  
    def get(self, key: str):
        """获取缓存"""
        # 先查本地缓存
        if key in self.local_cache:
            return self.local_cache[key]
  
        # 再查Redis
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
        except:
            pass
  
        return None
  
    def set(self, key: str, value: Any, ttl: int = 3600):
        """设置缓存"""
        # 本地缓存
        self.local_cache[key] = value
  
        # Redis缓存
        try:
            self.redis_client.setex(key, ttl, json.dumps(value))
        except:
            pass

# Step 2: 在SQL生成中添加缓存
cache = CacheManager()

async def generate_sql(question, intent, history):
    # 生成缓存键
    cache_key = cache.get_cache_key(question, json.dumps(history))
  
    # 检查缓存
    cached_sql = cache.get(cache_key)
    if cached_sql:
        logger.info("使用缓存的SQL")
        return cached_sql
  
    # 生成SQL
    sql = await llm_generate_sql(question, intent, history)
  
    # 缓存结果
    cache.set(cache_key, sql, ttl=86400)  # 缓存24小时
  
    return sql
```

#### 4.2 批量处理优化

**可执行步骤**：

```python
# Step 1: 批量LLM调用
async def batch_generate_sql(questions: List[str], batch_size: int = 5) -> List[str]:
    """批量生成SQL，减少API调用次数"""
    results = []
  
    for i in range(0, len(questions), batch_size):
        batch = questions[i:i+batch_size]
  
        # 构建批量Prompt
        batch_prompt = format_batch_prompt(batch)
  
        # 一次调用处理多个问题
        batch_results = await llm_client.chat(batch_prompt)
  
        # 解析批量结果
        sqls = parse_batch_results(batch_results)
        results.extend(sqls)
  
        # 控制速率
        await asyncio.sleep(0.5)
  
    return results

# Step 2: 并行处理PDF
async def parallel_parse_pdfs(pdf_paths: List[str], max_workers: int = 4):
    """并行解析多个PDF"""
    semaphore = asyncio.Semaphore(max_workers)
  
    async def parse_one(pdf_path):
        async with semaphore:
            return await parse_pdf(pdf_path)
  
    tasks = [parse_one(path) for path in pdf_paths]
    results = await asyncio.gather(*tasks)
    return results
```

---

### 5. 成本优化

#### 5.1 智能路由（预期降低：-30-50%成本）

**优化思路**：简单问题用便宜模型，复杂问题用强大模型。

**可执行步骤**：

```python
# Step 1: 问题复杂度评估
def estimate_complexity(question: str) -> str:
    """评估问题复杂度"""
    # 简单问题：单表单条件查询
    simple_patterns = [
        r'^.*的.*是多少$',
        r'^.*的.*是多少\?$',
    ]
  
    # 复杂问题：多表JOIN、聚合、子查询
    complex_patterns = [
        r'.*对比.*',
        r'.*排名.*',
        r'.*趋势.*',
        r'.*同比.*',
    ]
  
    for pattern in simple_patterns:
        if re.match(pattern, question):
            return 'simple'
  
    for pattern in complex_patterns:
        if re.search(pattern, question):
            return 'complex'
  
    return 'medium'

# Step 2: 模型路由
async def route_to_model(question: str, llm_configs: List[Dict]) -> LLMClient:
    """根据问题复杂度选择模型"""
    complexity = estimate_complexity(question)
  
    if complexity == 'simple':
        # 使用便宜的模型（如GLM-4-Flash）
        config = next((c for c in llm_configs if 'flash' in c['model'].lower()), llm_configs[0])
    elif complexity == 'complex':
        # 使用强大的模型（如DeepSeek-V3）
        config = next((c for c in llm_configs if 'v3' in c['model'].lower() or 'pro' in c['model'].lower()), llm_configs[-1])
    else:
        # 使用中等模型
        config = llm_configs[len(llm_configs)//2]
  
    return LLMClient(config)
```

#### 5.2 结果缓存策略

**可执行步骤**：

```python
# 在agent.py中添加结果缓存
class SmartQAAgent:
    def __init__(self, ...):
        self.result_cache = {}  # question -> response
  
    async def process_question(self, question: str, ...):
        # 检查缓存
        cache_key = self._get_cache_key(question)
        if cache_key in self.result_cache:
            logger.info("使用缓存结果")
            return self.result_cache[cache_key]
  
        # 处理问题
        response = await self._process_question_internal(question, ...)
  
        # 缓存结果（仅缓存简单查询）
        if self._is_cacheable(question, response):
            self.result_cache[cache_key] = response
  
        return response
```

---

### 6. 前端优化

#### 6.1 响应式设计优化

**可执行步骤**：

```typescript
// 文件：frontend/src/pages/ChatPage.tsx

// Step 1: 添加响应式布局
import { useMediaQuery } from 'react-responsive';

function ChatPage() {
  const isMobile = useMediaQuery({ maxWidth: 768 });
  
  return (
    <Layout>
      {!isMobile && <Sider />}  {/* 移动端隐藏侧边栏 */}
      <Content>
        {/* 自适应内容 */}
      </Content>
    </Layout>
  );
}

// Step 2: 优化图表显示
// 使用echarts-for-react替代matplotlib图片，支持交互
import ReactECharts from 'echarts-for-react';

function ChartDisplay({ data, type }) {
  const option = generateEChartsOption(data, type);
  return <ReactECharts option={option} style={{ height: '400px' }} />;
}
```

#### 6.2 性能优化

**可执行步骤**：

```typescript
// Step 1: 使用React.memo优化组件
const MessageItem = React.memo(({ message }) => {
  // ...
});

// Step 2: 虚拟滚动（处理长对话历史）
import { FixedSizeList } from 'react-window';

function MessageList({ messages }) {
  return (
    <FixedSizeList
      height={600}
      itemCount={messages.length}
      itemSize={100}
    >
      {({ index, style }) => (
        <div style={style}>
          <MessageItem message={messages[index]} />
        </div>
      )}
    </FixedSizeList>
  );
}

// Step 3: 代码分割
const KnowledgeBasePage = React.lazy(() => import('./pages/KnowledgeBasePage'));

function App() {
  return (
    <Suspense fallback={<Loading />}>
      <KnowledgeBasePage />
    </Suspense>
  );
}
```

---

### 7. 监控与评估

#### 7.1 添加评估指标

**可执行步骤**：

```python
# 文件：backend/core/evaluator.py（新建）

class PerformanceEvaluator:
    def __init__(self):
        self.metrics = {
            'sql_accuracy': [],  # SQL生成准确率
            'response_time': [],  # 响应时间
            'cost_per_query': [],  # 每次查询成本
        }
  
    def evaluate_sql(self, sql: str, expected_result: Any, actual_result: Any) -> float:
        """评估SQL准确性"""
        # 比较预期结果和实际结果
        if expected_result == actual_result:
            return 1.0
        # 计算相似度
        return calculate_similarity(expected_result, actual_result)
  
    def log_query(self, question: str, response_time: float, cost: float):
        """记录查询指标"""
        self.metrics['response_time'].append(response_time)
        self.metrics['cost_per_query'].append(cost)
  
    def generate_report(self) -> Dict:
        """生成评估报告"""
        return {
            'avg_response_time': np.mean(self.metrics['response_time']),
            'avg_cost': np.mean(self.metrics['cost_per_query']),
            'sql_accuracy': np.mean(self.metrics['sql_accuracy']),
        }
```

---

### 8. 部署优化

#### 8.1 Docker容器化

**可执行步骤**：

```dockerfile
# 文件：Dockerfile

FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制代码
COPY . .

# 启动服务
CMD ["python", "-m", "backend.api.server"]
```

```yaml
# 文件：docker-compose.yml

version: '3.8'
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./models:/app/models
    environment:
      - PYTHONUNBUFFERED=1
  
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
```

---

### 优化效果预期

实施以上优化后，预期可以达到：

| 指标           | 基线 | 优化后 | 提升    |
| -------------- | ---- | ------ | ------- |
| PDF解析准确率  | 85%  | 95%+   | +10%    |
| SQL生成准确率  | 80%  | 90%+   | +10%    |
| 知识库检索精度 | 70%  | 85%+   | +15%    |
| 平均响应时间   | 3-5s | 1-2s   | -60%    |
| API调用成本    | 100% | 50-70% | -30-50% |

---

### 开始优化

1. **选择优化方向**：根据您的需求和资源，选择1-2个方向重点优化
2. **逐步实施**：不要一次性改动太多，逐步测试和验证
3. **记录效果**：记录优化前后的指标对比
4. **持续迭代**：根据实际效果调整优化策略

**⚠⚠⚠注意，本项目仅供学习参考，不能作为最终竞赛方案！！！！祝您优化顺利！** 🚀

---

## 技术栈

| 组件     | 技术                  | 版本   |
| -------- | --------------------- | ------ |
| 后端框架 | FastAPI               | 0.100+ |
| 数据库   | SQLite                | 内置   |
| LLM调用  | OpenAI SDK            | 1.0+   |
| PDF解析  | pdfplumber            | 0.10+  |
| 嵌入模型 | sentence-transformers | 2.2+   |
| 可视化   | matplotlib            | 3.7+   |
| 前端框架 | React + TypeScript    | 18.2+  |
| UI组件库 | Ant Design            | 5.15+  |
| 构建工具 | Vite                  | 5.1+   |
| 状态管理 | Zustand               | 4.5+   |
