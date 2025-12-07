# 🚀 arXiv-crawler-ai-enhanced

> [!CAUTION]
> 若您所在法域对学术数据有审查要求，谨慎运行本代码；任何二次分发版本必须履行合规审查（包括但不限于原始论文合规性、AI合规性）义务，否则一切法律后果由下游自行承担。

> [!CAUTION]
> If your jurisdiction has censorship requirements for academic data, run this code with caution; any secondary distribution version must remove the entrance accessible to China and fulfill the content review obligations, otherwise all legal consequences will be borne by the downstream.

## 📁 仓库说明

本仓库是**daily-arXiv-ai-enhanced**和**arxiv_crawler**两个仓库的融合版本，整合了两个项目的核心功能，实现了一个强大、灵活的arxiv论文处理系统：

- **daily-arXiv-ai-enhanced**：提供了AI增强的arxiv论文阅读体验，包括自动化爬取、AI摘要生成和美观的Web界面
- **arxiv_crawler**：提供了强大的arxiv论文爬取功能，支持异步快速爬取，自定义分类、关键词搜索和多语言翻译

通过融合这两个仓库，我们实现了更强大、更灵活的arxiv论文处理系统，论文数据使用SQLite数据库管理，同时保持了代码的可维护性和扩展性。

## ✨ 核心功能

🎯 **无需基础设施**
- 利用GitHub Actions和Pages - 无需服务器
- 部署和使用完全免费
- 零运维成本

🤖 **智能AI摘要**
- 每日自动爬取论文，使用DeepSeek生成结构化摘要
- 成本效益高：每天仅需约0.2元
- 支持可配置的多线程并行处理，性能优异
- 结构化输出：包括tldr、motivation、method、result、conclusion等

💫 **智能阅读体验**
- 基于兴趣的个性化论文高亮
- 跨设备兼容（桌面端和移动端）
- 本地存储偏好设置，保护隐私
- 灵活的日期范围筛选
- 支持关键词搜索

🔧 **强大的爬虫支持**
- 高级arxiv_crawler模块，配置选项丰富
- 易用的run_crawler.py脚本
- 支持生成JSONL文件和AI增强的JSONL文件
- 通过环境变量高度可配置
- 支持全量更新和增量更新两种模式

📊 **数据管理**
- 使用SQLite数据库存储论文数据
- 支持数据的增删改查
- 高效的日期索引
- 支持数据导出为多种格式

## 📦 本地部署

### 前置要求
- Python 3.8+（推荐3.10+）
- Git
- 可选：Node.js（用于高级HTTP服务器）

### 安装步骤

1. **克隆仓库**：
   ```bash
   git clone https://github.com/dw-dengwei/daily-arXiv-ai-enhanced.git
   cd daily-arXiv-ai-enhanced
   ```

2. **创建并激活conda环境**：
   ```bash
   # 创建conda环境
   conda create -n arxiv-crawler python=3.10 -y
   
   # 激活环境（Windows/Linux/Mac通用）
   conda activate arxiv-crawler
   ```

3. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

4. **配置环境变量**：
   ```bash
   cp .env.example .env
   # 编辑.env文件，配置API密钥和其他参数
   ```

### 环境变量配置

本项目通过环境变量进行全面配置，所有关键参数均可在`.env`文件中设置：

```env
# DeepSeek API配置
OPENAI_API_KEY="your-api-key"          # DeepSeek API密钥
OPENAI_BASE_URL="https://api.deepseek.com"  # DeepSeek API基础URL
MODEL_NAME="deepseek-chat"           # 默认模型名称
LANGUAGE="Chinese"                   # AI生成内容的语言

# 爬虫行为配置
MAX_WORKERS=4                        # AI增强的最大并行数
CRAWL_ALL=false                      # 爬取模式：true表示全量更新，false表示增量更新
CRAWL_DATE=""                        # 指定爬取日期，格式为YYYY-MM-DD，留空表示今天

# 论文筛选配置
CATEGORY_WHITELIST=cs.CV,cs.AI,cs.DS,cs.ET,cs.HC,cs.NE,cs.RO,cs.SD,eess.AS,eess.IV  # 论文分类白名单
CATEGORY_BLACKLIST=                  # 论文分类黑名单，使用逗号分隔
OPTIONAL_KEYWORDS=cs.CV,cs.AI,cs.DS,cs.ET,cs.HC,cs.NE,cs.RO,cs.SD,eess.AS,eess.IV  # 可选关键词

# 翻译配置
TRANS_TO=zh-CN                       # 翻译目标语言，留空表示不翻译
TRANSLATION_SEMAPHORE=80             # 翻译并发限制

# 网络配置
PROXY=                               # 代理设置，格式为http://127.0.0.1:7890，留空表示不使用代理

# 爬取参数配置
STEP=50                              # 每页爬取数量

# 部署与安全配置
ACCESS_PASSWORD=                     # 页面访问密码，留空表示不使用密码保护
EMAIL=your-email@example.com         # GitHub提交邮箱，用于GitHub Actions自动部署
NAME=your-github-username            # GitHub提交用户名，用于GitHub Actions自动部署
```

### 本地运行时设置变量的方法

#### 环境变量来源与优先级

本地运行时，环境变量的来源和优先级如下：
- **GitHub Actions中**：git secrets > .env文件
- **本地开发时**：系统环境变量/终端临时设置 > .env文件

这意味着如果在终端或系统中设置了环境变量，会优先使用这些值，否则使用`.env`文件中的值。

#### 本地运行时设置变量的方法

##### 1. 通过.env文件设置（推荐）

这是最常用的方法，适合本地开发和测试：

```bash
# 复制示例文件
cp .env.example .env

# 使用文本编辑器编辑.env文件
# Windows: notepad .env
# Linux/Mac: nano .env 或 vim .env

# 修改后保存文件，重新运行程序即可生效
```

##### 2. 通过终端临时设置

适合临时测试不同配置：

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="your-actual-api-key"
$env:OPENAI_BASE_URL="https://api.deepseek.com"
$env:MODEL_NAME="deepseek-chat"
python run_crawler.py

# Linux/Mac
OPENAI_API_KEY="your-actual-api-key" OPENAI_BASE_URL="https://api.deepseek.com" MODEL_NAME="deepseek-chat" python run_crawler.py

# 或分多行设置
export OPENAI_API_KEY="your-actual-api-key"
export OPENAI_BASE_URL="https://api.deepseek.com"
export MODEL_NAME="deepseek-chat"
python run_crawler.py
```

##### 3. 通过系统环境变量设置

适合长期使用，所有终端会话中都会生效：

- **Windows**：设置 > 系统 > 关于 > 高级系统设置 > 环境变量
- **Linux/Mac**：修改`~/.bashrc`或`~/.zshrc`文件，添加：
  ```bash
export OPENAI_API_KEY="your-actual-api-key"
export OPENAI_BASE_URL="https://api.deepseek.com"
export MODEL_NAME="deepseek-chat"
  ```
  然后运行`source ~/.bashrc`或`source ~/.zshrc`使设置生效

#### 本地运行时测试环境变量

你可以通过以下命令测试环境变量是否被正确读取：

```bash
# 查看环境变量配置
python -c "
import os
from dotenv import load_dotenv
if os.path.exists('.env'):
    load_dotenv(override=False)
print('OPENAI_API_KEY:', os.environ.get('OPENAI_API_KEY', '[NOT SET]'))
print('OPENAI_BASE_URL:', os.environ.get('OPENAI_BASE_URL', '[NOT SET]'))
print('MODEL_NAME:', os.environ.get('MODEL_NAME', '[NOT SET]'))
"

# 运行帮助命令，确认程序能正常加载
python run_crawler.py --help
```

#### 本地运行示例

```bash
# 使用.env文件配置运行
python run_crawler.py --date 2024-12-06

# 使用终端临时设置运行（Windows PowerShell）
$env:OPENAI_API_KEY="your-actual-api-key"
python run_crawler.py --date 2024-12-06 --all

# 使用终端临时设置运行（Linux/Mac）
OPENAI_API_KEY="your-actual-api-key" python run_crawler.py --date 2024-12-06 --all
```

## 🚀 运行爬虫

### 使用run_crawler.py脚本

```bash
# 运行爬虫，使用默认配置（从环境变量读取）
python run_crawler.py

# 运行爬虫，指定日期
python run_crawler.py --date 2025-12-05

# 运行爬虫，全量更新(构建个人本地数据库，首次运行先执行全量更新)
python run_crawler.py --all

# 结合使用：全量更新+指定日期
python run_crawler.py --all --date 2025-12-05
```

### 参数说明
- `--all`：**标志参数**，不需要跟值。当出现该参数时，表示全量更新当月论文；不出现时，表示增量更新当天论文
- `--date`：指定要爬取的日期，格式为YYYY-MM-DD，留空表示今天
- 优先级：命令行参数 > 环境变量 > 默认值

### 脚本输出

运行爬虫后，你将看到类似以下的输出：

```
--- 环境变量配置 ---
CRAWL_ALL: false
CRAWL_DATE:
MAX_WORKERS: 20
CATEGORY_BLACKLIST:
CATEGORY_WHITELIST: cs.CV,cs.AI,cs.DS,cs.ET,cs.HC,cs.NE,cs.RO,cs.SD,eess.AS,eess.IV
OPTIONAL_KEYWORDS: cs.CV,cs.AI,cs.DS,cs.ET,cs.HC,cs.NE,cs.RO,cs.SD,eess.AS,eess.IV
TRANS_TO: zh-CN
PROXY: http://127.0.0.1:10808
STEP: 50
------------------

开始爬取 2025-12-05 的论文数据，模式：增量更新，AI并行数：20
[22:49:40] last update: 2025-12-06 13:39:01, next arxiv update: 2025-12-08                        arxiv_crawler.py:225
           UTC now: 2025-12-06 14:49:39                                                           arxiv_crawler.py:228
           Your database is already up to date.                                                   arxiv_crawler.py:231
生成markdown文件...
[22:49:40] Output 2025-12-05.md completed. 196 papers chosen, 0 papers filtered                             paper.py:515
生成标准JSONL文件...
           Output 2025-12-05.jsonl completed. 196 papers exported                                         paper.py:590
生成AI增强的JSONL文件...
生成AI增强的JSONL文件失败，但将继续执行: 'PaperExporter' object has no attribute 'to_ai_enhanced_jsonl'
更新assets/file-list.txt...
已更新file-list.txt，添加了 3 个新文件
爬取和生成完成！
```

## 🌐 本地预览

### 运行本地HTTP服务

在本地运行HTTP服务，方便预览生成的论文内容：

#### 方法1：使用Python内置HTTP服务器（推荐，无需额外依赖）
```bash
# 在项目根目录运行
python -m http.server 8000
```

然后在浏览器中访问：`http://localhost:8000`

#### 方法2：使用http-server（支持自动重载）
```bash
# 先安装http-server
npm install -g http-server

# 在项目根目录运行，启用自动重载
http-server -p 8000 -o -c-1
```

然后在浏览器中访问：`http://localhost:8000`

#### 方法3：使用live-server（支持实时预览）
```bash
# 先安装live-server
npm install -g live-server

# 在项目根目录运行
live-server --port=8000
```

然后在浏览器中访问：`http://localhost:8000`

### 访问本地服务

1. 运行HTTP服务后，在浏览器中输入对应的URL（如`http://localhost:8000`）
2. 页面会显示论文列表，点击任意论文可以查看详细内容
3. 使用页面顶部的搜索框和筛选器查找感兴趣的论文
4. 本地服务仅在您的计算机上可用，不会被外部访问

## 🛠️ 调试与故障排除

### 常见问题与解决方案

#### 问题1：生成AI增强文件失败
**错误信息**：`'PaperExporter' object has no attribute 'to_ai_enhanced_jsonl'`

**解决方案**：
1. 检查`paper.py`文件中是否存在`to_ai_enhanced_jsonl`方法
2. 确保代码是最新版本，尝试重新克隆仓库
3. 检查`arxiv_crawler.py`中是否正确调用了该方法

#### 问题2：敏感词检测超时
**错误信息**：`Sensitive check error: HTTPSConnectionPool(host='spam.dw-dengwei.workers.dev', port=443): Read timed out. (read timeout=5)`

**解决方案**：
1. 编辑`ai/enhance.py`文件，修改敏感词检测的超时时间
2. 或者暂时禁用敏感词检测（注释相关代码）

#### 问题3：数据库连接失败
**错误信息**：`sqlite3.OperationalError: unable to open database file`

**解决方案**：
1. 检查数据库文件的权限
2. 确保当前用户有读写权限
3. 尝试重新创建数据库

#### 问题4：爬取速度慢
**解决方案**：
1. 调整`STEP`参数，增加每页爬取数量
2. 调整`MAX_WORKERS`参数，增加并行数
3. 检查网络连接和代理设置

#### 问题5：AI增强速度慢
**解决方案**：
1. 调整`MAX_WORKERS`参数，增加AI生成的并行数
2. 检查API密钥和网络连接
3. 考虑使用性能更好的AI模型

### 调试工具与技巧

1. **查看日志**：运行爬虫时，控制台会输出详细的日志信息，包括爬取进度、错误信息等
2. **启用调试模式**：在`run_crawler.py`中添加`import logging; logging.basicConfig(level=logging.DEBUG)`
3. **使用数据库查看工具**：如SQLiteBrowser，查看数据库中的数据
4. **测试单个组件**：编写简单的测试脚本，测试单个组件的功能
5. **检查API响应**：使用Postman或curl测试API响应

## 🌐 GitHub Actions 线上部署

### 自动化部署流程

本项目使用GitHub Actions实现自动化部署，每天自动爬取arxiv论文并生成AI增强内容，然后部署到GitHub Pages。

### 配置步骤

1. **Fork仓库**：Fork本仓库到您自己的GitHub账户。

2. **配置环境变量**：
   - **本地开发**：直接修改仓库中的`.env`文件，配置所有必要参数
   - **GitHub Actions部署**：需要在GitHub仓库中配置Secrets（推荐）

3. **配置GitHub Secrets**：
   - 进入您的仓库 → Settings → Secrets and variables → Actions
   - 点击"New repository secret"，添加以下Secrets：
     - `OPENAI_API_KEY`：DeepSeek API密钥
     - `OPENAI_BASE_URL`：DeepSeek API基础URL（默认：https://api.deepseek.com）
     - `MODEL_NAME`：使用的大模型名称（默认：deepseek-chat）
   - 其他配置参数仍可在`.env`文件中直接修改

4. **启用GitHub Pages**：
   - 进入您的仓库 → Settings → Pages
   - 在Build and deployment部分，设置Source为"Deploy from a branch"
   - 设置Branch为"main"，目录为"/(root)"
   - 点击Save

5. **运行Workflow**：
   - 进入您的仓库 → Actions
   - 选择"arxiv-daily-ai-enhanced" workflow
   - 点击"Run workflow"按钮，手动触发第一次运行

### 自定义部署

- **修改爬取频率**：编辑`.github/workflows/run.yml`文件，修改`schedule`部分可以调整爬取频率
- **修改爬取分类**：直接修改`.env`文件中的`CATEGORY_WHITELIST`变量
- **修改AI模型**：直接修改`.env`文件中的`MODEL_NAME`变量
- **修改其他配置**：所有配置参数均可在`.env`文件中直接修改

## 📁 项目结构

```
daily-arXiv-ai-enhanced/
├── .github/              # GitHub Actions配置
│   └── workflows/
│       └── run.yml        # 自动化部署配置
├── ai/                   # AI增强模块
│   ├── enhance.py        # AI增强核心代码
│   ├── structure.py      # AI输出结构定义
│   ├── system.txt        # 系统提示词
│   └── template.txt      # 提示词模板
├── arxiv_crawler/        # 爬虫模块
│   ├── arxiv_crawler.py  # 爬虫核心代码
│   ├── async_translator.py  # 异步翻译模块
│   ├── categories.py     # 分类映射
│   └── paper.py          # 论文数据结构和数据库操作
├── assets/               # 静态资源
│   └── file-list.txt     # 生成文件列表
├── css/                  # CSS样式文件
├── data/                 # 生成的数据文件
│   ├── YYYY-MM-DD.jsonl  # 标准论文数据
│   └── YYYY-MM-DD_AI_enhanced_*.jsonl  # AI增强的论文数据
├── output_md/            # 生成的Markdown文件
│   └── YYYY-MM-DD.md     # 每日论文Markdown文件
├── papers.db             # SQLite数据库文件
├── .env                  # 环境变量配置
├── .env.example          # 环境变量示例
├── index.html            # Web界面入口
├── run_crawler.py        # 爬虫运行脚本
├── requirements.txt      # 项目依赖
└── README.md             # 项目说明文档
```

## 🔧 核心功能模块

### 1. 爬虫模块（arxiv_crawler）

#### 主要功能
- 从arxiv.org爬取论文数据
- 支持按日期范围、分类、关键词筛选
- 提供异步翻译功能
- 支持全量更新和增量更新两种模式
- 使用异步HTTP请求提高爬取效率

#### 核心文件
- `arxiv_crawler.py`：爬虫核心代码，处理HTTP请求和HTML解析
- `async_translator.py`：异步翻译模块，使用Google Translate API
- `categories.py`：分类映射，处理arxiv分类和中文名称的映射
- `paper.py`：论文数据结构和数据库操作

### 2. AI增强模块（ai）

#### 主要功能
- 使用大模型生成论文摘要、动机、方法、结果等
- 支持多语言生成
- 支持并行处理，提高效率
- 提供结构化输出
- 包含敏感词检测功能

#### 核心文件
- `enhance.py`：AI增强核心代码，处理AI生成和敏感词检测
- `structure.py`：AI输出结构定义，使用Pydantic模型
- `system.txt`：系统提示词，指导AI生成内容
- `template.txt`：提示词模板，包含生成内容的格式和要求

### 3. 数据管理模块

#### 主要功能
- 使用SQLite数据库存储论文数据
- 支持数据的增删改查
- 高效的日期索引
- 支持数据导出为多种格式

#### 核心文件
- `paper.py`：包含`PaperDatabase`类，处理数据库操作
- `papers.db`：SQLite数据库文件，存储所有论文数据

### 4. Web界面模块

#### 主要功能
- 美观的论文浏览界面
- 支持按关键词搜索
- 支持按日期范围筛选
- 支持个性化高亮
- 支持跨设备访问

#### 核心文件
- `index.html`：Web界面入口
- `css/`：CSS样式文件
- `assets/file-list.txt`：生成文件列表，用于Web界面加载

## 📊 输出文件格式

### JSONL文件

#### 标准JSONL文件（data/YYYY-MM-DD.jsonl）
包含论文的基础信息：
```json
{
  "id": "2512.05117",
  "pdf": "https://arxiv.org/pdf/2512.05117",
  "abs": "https://arxiv.org/abs/2512.05117",
  "authors": ["Author1", "Author2"],
  "title": "The Universal Weight Subspace Hypothesis",
  "categories": ["cs.LG"],
  "comment": null,
  "summary": "We show that deep neural networks trained across diverse tasks exhibit remarkably similar low-dimensional parametric subspaces..."
}
```

#### AI增强JSONL文件（data/YYYY-MM-DD_AI_enhanced_Chinese.jsonl）
包含论文的基础信息和AI生成的结构化摘要：
```json
{
  "id": "2512.05117",
  "pdf": "https://arxiv.org/pdf/2512.05117",
  "abs": "https://arxiv.org/abs/2512.05117",
  "authors": ["Author1", "Author2"],
  "title": "The Universal Weight Subspace Hypothesis",
  "categories": ["cs.LG"],
  "comment": null,
  "summary": "We show that deep neural networks trained across diverse tasks exhibit remarkably similar low-dimensional parametric subspaces...",
  "AI": {
    "tldr": "本文证明了深度神经网络在不同任务上训练时会表现出相似的低维参数子空间",
    "motivation": "理解深度神经网络的学习机制是深度学习领域的重要问题",
    "method": "通过对1100多个模型进行模式谱分析",
    "result": "发现了捕捉大部分方差的通用子空间",
    "conclusion": "这一发现为模型重用和多任务学习提供了新的思路"
  }
}
```

### Markdown文件

生成的Markdown文件（output_md/YYYY-MM-DD.md）包含当日所有论文的详细信息，格式如下：

```markdown
# 论文全览：2025-12-05

共有196篇相关领域论文, 另有0篇其他

## 计算机视觉(cs.CV:Computer Vision)

【2512.05117】The Universal Weight Subspace Hypothesis
- **标题**: 通用权重子空间假设
- **链接**: https://arxiv.org/abs/2512.05117
> **作者**: Author1, Author2
> **摘要**: 我们证明了深度神经网络在不同任务上训练时会表现出非常相似的低维参数子空间...
> **Abstract**: We show that deep neural networks trained across diverse tasks exhibit remarkably similar low-dimensional parametric subspaces...

...
```

## 🚀 使用案例

### 案例1：每日自动更新

**目标**：每天自动爬取最新论文，生成AI增强内容，并部署到GitHub Pages

**实现步骤**：
1. Fork仓库到自己的GitHub账户
2. 配置`.env`文件，添加API密钥和其他参数
3. 启用GitHub Pages
4. 运行GitHub Actions Workflow
5. 访问GitHub Pages地址，查看每日更新

### 案例2：本地爬取特定分类

**目标**：在本地爬取特定分类的论文，生成AI增强内容，并使用Web界面浏览

**实现步骤**：
1. 克隆仓库到本地
2. 配置`.env`文件，设置`CATEGORY_WHITELIST`为感兴趣的分类
3. 运行`python run_crawler.py --all`，全量更新数据
4. 运行本地HTTP服务器
5. 在浏览器中访问，浏览和搜索论文

### 案例3：自定义AI增强

**目标**：使用自定义的AI模型和提示词，生成个性化的论文摘要

**实现步骤**：
1. 克隆仓库到本地
2. 配置`.env`文件，设置自定义的`MODEL_NAME`和`OPENAI_BASE_URL`
3. 修改`ai/template.txt`和`ai/system.txt`，自定义提示词
4. 运行`python run_crawler.py --date 2025-12-05`，测试特定日期的AI增强
5. 查看生成的AI增强文件

### 案例4：数据导出与分析

**目标**：将爬取的论文数据导出为CSV格式，进行数据分析

**实现步骤**：
1. 克隆仓库到本地
2. 运行`python run_crawler.py --all`，全量更新数据
3. 使用SQLiteBrowser打开`papers.db`文件
4. 执行SQL查询，导出数据为CSV格式
5. 使用Excel或Python进行数据分析


## 📝 许可证

MIT License - 详见[LICENSE](LICENSE)文件。

## 🙏 致谢

感谢以下项目和贡献者：

- **daily-arXiv-ai-enhanced**：提供了AI增强和Web界面功能
- **arxiv_crawler**：提供了强大的arxiv爬取功能
- 所有为本项目贡献代码和提出建议的开发者
- DeepSeek AI：提供了强大的AI模型支持
- arXiv：提供了丰富的学术论文资源

## ⭐ Star History

[![Stargazers over time](https://starchart.cc/scouthe/arxiv_crawler_ai_enhanced.svg?variant=adaptive)](https://starchart.cc/scouthe/arxiv_crawler_ai_enhanced)

## 📞 联系方式

如有问题或建议，欢迎通过以下方式联系我们：

- GitHub Issues：https://github.com/scouthe/arxiv_crawler_ai_enhanced/issues
- GitHub Discussions：https://github.com/scouthe/arxiv_crawler_ai_enhanced/discussions

## 📚 相关资源

- [arxiv.org](https://arxiv.org/)：原始论文资源
- [DeepSeek API](https://platform.deepseek.com/)：AI模型API
- [GitHub Actions](https://docs.github.com/en/actions)：自动化部署
- [GitHub Pages](https://pages.github.com/)：静态网站托管
- [SQLite](https://www.sqlite.org/index.html)：轻量级数据库

## 📈 项目统计

- 代码行数：约5000行
- 核心功能模块：4个
- 支持的AI模型：所有OpenAI兼容模型
- 支持的语言：中文、英文等
- 日处理能力：约1000篇论文
- 平均AI增强时间：每篇约2秒

---

**arxiv-crawler-ai-enhanced** - 让arxiv论文阅读更智能、更高效！ 🚀