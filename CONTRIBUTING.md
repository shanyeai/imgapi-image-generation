# 贡献与反馈 / Contributing

欢迎报告可复现的接入问题，或提出商品图、内容配图等新场景。提交前请查阅现有 Issues，尽量一次只处理一个问题。

## 开始修改

```bash
npm test
python -m pip install -r python/requirements.txt
python -m unittest discover -s tests -p "test_*.py"
```

测试不得依赖真实 CardKey 或付费任务。示例改动请同步中英文 README 中受影响的命令，并补充能验证行为的离线测试。JSON 场景仅放公开、可分享的提示词，不包含客户图片、真实 Key 或签名 URL。

客户端由 imgAPI 文档提取；接口契约变化时请提供文档依据。不要为处理超时加入自动重复提交，不更改生产端点来绕过错误，也不要把大规模框架或额外服务作为运行基础示例的前提。

此仓库暂未添加开源许可证。涉及代码再分发或授权贡献时，请先与维护者明确许可范围。

English reports and pull requests are welcome. Include the runtime version, repository commit, a minimal reproduction and offline test results. Never share credentials or private image URLs. Keep paid generation out of tests and preserve the submit-once behavior. No open-source license has been granted; clarify permissions with the maintainer where required.
