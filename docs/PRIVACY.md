# 发布内容与身份隔离

公开树由文件白名单组成：原创补丁、辅助 Java 代码、构建脚本、资源校验清单和整理后的说明文档。

原始 APK、修改 APK、模型、反编译产物、截图、设备日志、个人数据库、工具缓存、签名密钥和发布凭证均不在源码树内。开发过程的 Git 历史没有导入本仓库。

提交署名统一为 `Contributors`，邮箱为 `contributors@users.invalid`；该保留域名用于避免误关联真实邮箱，不提供邮件收件服务。初始提交使用统一 UTC 时间，不包含开发时段或本地时区。

## 后续提交

```sh
git config --local user.name Contributors
git config --local user.email contributors@users.invalid
git config --local commit.gpgsign false
git config --local core.hooksPath .githooks
git add .
python scripts/publish_check.py
python scripts/publish_check.py --history
```

发布检查针对暂存区或全部本地分支的提交，限制路径、文件类型和大小，扫描个人路径、邮箱、网络地址、常见凭证并校验提交身份。可以用环境变量 `PUBLISH_DENYLIST_FILE` 指定本机私有 JSON 字符串数组，额外拒绝自己的姓名、设备编号等；该文件不得加入仓库。

新增公开文件需要先人工检查，再更新白名单。钩子依赖本机 Python，且不会随克隆自动启用。自动检查无法理解所有自然语言中的身份线索，仍需人工复核。

化名账号下的公开仓库会彼此关联。公开记录清理不能消除托管平台掌握的账号、授权、访问和网络记录，也不能保证无法关联真实身份。独立签名证书的公钥可关联使用同一签名的 APK 版本；签名私钥始终只留在本地。
