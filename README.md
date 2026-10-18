# 麦麦QQ空间说说 🌤️

让麦麦按你的指令发纯文字说说，也能按人设、时间和概率自己发布日常感想。

> 麦麦，发条说说，内容是：今天也要开开心心。
>
> 麦麦，写一条关于秋天的说说并发出去。

## 功能

- `publish_qzone`：提供 `content` 直接发原文，或提供 `topic` 让麦麦构思后发布。
- 仅支持1–1000字纯文字；收到说说 `tid` 才报告成功。
- 自主内容读取全局人设，不读取私聊、群聊记录；最近5条自身说说用于避免重复。
- 状态和限额在重启后保留，接口失败或回执不明确时不自动重发。

## 自主发布默认设置

**默认开启自主发布，默认所有人可见。** 不需要自动发布时，将 `[autonomous] enabled` 改为 `false`。

| 设置 | 默认值 |
| --- | --- |
| 时间 | 上海时间09:00（含）至23:00（不含） |
| 概率 | 每小时20% |
| 最小间隔 | 4小时 |
| 每日上限 | 2次自主发布尝试 |
| 查看权限 | 1：所有人可见 |

首次启用从下一整点开始；关闭麦麦期间不会运行，不补发错过的小时。
失败也占用自主发布额度，避免网络结果不明时重复发布。手动发布不占自主额度。
随机概率不保证每天一定发布，模型生成会使用麦麦已配置的模型额度。
`start_hour` 必须小于 `end_hour`，不支持跨午夜时段；修改后可在插件管理重新启用。

`visibility` 支持 `1` 所有人、`4` 好友、`64` 仅自己。
状态文件在 `data/plugins/krissrty.qzone/schedule_state.json`，请勿在运行中删除。
工具没有额外的主人白名单，遵循麦麦现有聊天及工具权限。
自主生成通过提示词要求避免隐私和虚构经历，仍需自行评估模型输出。
**仅支持SnowLuma客户端，不支持NapCat客户端**；QQ空间登录状态及账号限制可能影响发布。

## 环境要求

- MaiBot 1.2.5 及以上的 1.x 版本，maibot-plugin-sdk 2.6.x–2.x。
- 已安装并连接 [SnowLuma 适配器](https://github.com/Mai-with-u/MaiBot-SnowLuma-Adapter)，插件 ID 为 `maibot-team.snowluma-adapter`。
- 这是第三方插件，不会自动安装或配置适配器。声明的兼容范围不代表每个版本组合均经过实测。

## 安装

1. 点击本仓库 **Code → Download ZIP**，解压。
2. 将包含 `plugin.py` 和 `_manifest.json` 的文件夹放进麦麦的 `plugins/maibot-qzone/`，避免多套一层目录。
3. 重启麦麦，在插件管理中确认“麦麦说说：手动与概率自主发布”加载成功。
4. 需要自定义时，将 `config.example.toml` 复制为 `config.toml` 后修改；不要覆盖已有配置。

插件 ID：`krissrty.qzone`。本地旧版 `local.*` 插件用户应停用旧版后再安装，避免同名工具重复。

## 测试

使用麦麦自带的 Python（需包含 maibot_sdk），在仓库目录运行：

```console
python -m unittest discover -s tests
```

测试使用模拟接口，不会真实发送QQ消息或发表说说。测试通过不代表当前QQ账号的实际接口可用。

## 反馈与许可

问题请提交 [Issues](https://github.com/krissrty/maibot-qzone/issues)，附麦麦/SDK/适配器版本和脱敏日志，勿上传Token、完整配置或聊天数据库。

[MIT License](LICENSE)。
