# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- 新增 FastAPI 后端服务，支持环境变量在线管理
- 新增 `env_manager.html` 前端页面，用于可视化管理环境变量
- 在 API 服务器中添加 `/env-vars` 和 `/env-manager` 端点
- 更新 README.md，详细记录 Web 界面和 API 端点

### Changed
- 更新 `requirements.txt`，添加精确版本号和缺失的 Web 服务依赖
- 优化 `run_crawler.py` 中的 `update_file_list` 函数

### Fixed
- 修复 `file-list.txt` 中不必要添加 English.json 的问题

## [1.1.0] - 2025-12-06

### Added
- 新增本地爬虫支持，使用 `run_crawler.py` 脚本
- 新增 `arxiv_crawler` 模块，支持本地运行
- 支持生成 JSONL 文件和 AI 增强的 JSONL 文件
- 添加 `requirements.txt` 文件，方便本地部署
- 完善项目文档，添加本地部署指南

### Changed
- 提高 AI 增强功能的处理速度，从单线程改为 4 线程
- 更新 README.md，添加本地部署和使用说明
- 优化 `_row_factory` 方法，解决直接运行 paper.py 时的警告

### Fixed
- 修复中文摘要不显示的问题，正确处理 SQLite Row 对象
- 修复 AI 增强功能，添加 API 密钥和基础 URL 配置
- 修复 `add_papers` 方法中的数据插入顺序
- 修复 `from_row` 方法，正确加载翻译字段

## [1.0.0] - 2024-09-10

### Added
- 初始版本发布
- 支持 GitHub Actions 自动爬取 arXiv 论文
- 支持 DeepSeek API 生成论文摘要
- 支持静态网站展示
- 支持个性化高亮和过滤

### Changed
- 无

### Fixed
- 无

[Unreleased]: https://github.com/dw-dengwei/daily-arXiv-ai-enhanced/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/dw-dengwei/daily-arXiv-ai-enhanced/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/dw-dengwei/daily-arXiv-ai-enhanced/releases/tag/v1.0.0