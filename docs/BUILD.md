# 本地构建

当前固定支持百度 Android 输入法 `13.3.16.2`、版本号 `1177`，输出 ARM64 安装包。补丁依赖本版本具体类结构和资源编号，不适用于随意替换的新版原包。

## 工具与输入

- Python 3.11 或更新版本；验证环境使用 Python 3.14。
- JDK 21，设置 `JAVA_HOME`。
- Android SDK：Build Tools 36.1.0、Platform android-36，设置 `ANDROID_SDK_ROOT`。
- Apktool 3.0.3 JAR，默认放到 `tools/apktool_3.0.3.jar`，或设置 `APKTOOL_JAR`。
- JADX 1.5.6 的 all JAR，默认 `tools/jadx-1.5.6-all.jar`，或设置 `JADX_JAR`。

`prepare.py` 固定校验原始 APK 和两个 JAR 的 SHA-256；工具需自行从对应官方项目获取。源码仓库不附带它们。

原包放在 `inputs/baiduinput_AndroidPhone_1000e.apk`，SHA-256 必须为：

```text
e83a5a0f48e147e1717fd54de8f56087a628bc28643a56286bf0c3e9a01af033
```

## 执行

```sh
python prepare.py --check
python prepare.py
python scripts/build_experiment.py
```

解包生成 `audit/decoded/`。构建将从 `resource-manifest.json` 指定的公开资源地址取得匹配离线模型，固定校验大小和 SHA-256。构建电脑需要下载资源；安装到手机后的输入法没有联网权限，模型在 APK 内。

已有资源也可提前放入 `audit/offline-voice/offline_voice_release_64.zip`，构建时校验后直接使用。地址失效或文件变化时停止，不自动改用不明来源。

输出：

- `dist/BaiduOffline-0.2-arm64.apk`
- `dist/SHA256SUMS.txt`
- `dist/build-verification.json`

第一次构建在 `.local/signing/` 创建通用证书主体的新私钥。该目录用于后续版本签名，务必本地妥善保管，不能上传。原始资源、输入核心和 ARM64 原生库保持原字节；兼容参数与界面入口通过版本固定的补丁处理。

诊断构建：

```sh
python scripts/build_experiment.py --debug
```

诊断包启用 Android 调试和私有异常记录，只用于本机排错，不作为公开发布包。构建脚本不会连接手机、安装应用或删除手机数据。

工具路径可通过环境变量配置，不要把自己的绝对目录、账号或凭证写进源码。
