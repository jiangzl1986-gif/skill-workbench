# 参与完善

请先描述使用场景和预期行为，再附最小公开示例。Issues 适合问题与建议；Pull Request 适合可检查的代码和文档修改。

不要上传私有 Skill、提示词、剧本、截图中的本机路径、密钥、账号资料或生产数据库。程序的测试资料须自行编写或有明确公开许可。

开发准备与验证：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
.\.venv\Scripts\python.exe -B -X utf8 -m pytest -q
```

前端构建使用 `tools/build_frontend.py`。运行时只能绑定本机，禁止在无新设计和审核时改成公网服务。

修改来源、同步、组装或导出逻辑时，验证正向和反向场景，包括原字节不变、版本身份、过期草稿、未选依赖、错误父子位置、大小界限和路径越界。测试通过不替代导入者 Skill 的业务语义或生产验收。

请保留依赖许可。使用 MIT 贡献自己有权提供的程序和示例；导入者的内容不属于仓库的程序许可。
