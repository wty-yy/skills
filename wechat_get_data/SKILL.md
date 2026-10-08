---
name: wechat_get_data
description: Read local WeChat Linux 4.x chat data and recover original emoji images from an authorized running WeChat session. Use for locating messages, querying a specified conversation, or exporting a chat sticker from local xwechat_files databases and process memory.
---

# WeChat Get Data

读取 Linux 微信 4.x 本地聊天记录，定位指定会话的表情消息，导出经过 MD5 校验的原始文件。适用于已登录、正在运行的官方 Linux 微信；其他平台和版本需要重新确认格式。

## 使用

1. 找到微信 PID 和账号目录。常见目录为 `~/Documents/xwechat_files/<account>`、`~/文档/xwechat_files/<account>`；使用当前环境的实际路径，不沿用过去的账号名或 PID。
2. 确定会话、时间范围和目标类型。用户已指定范围时直接执行，不扩大为整个账号的聊天导出。
3. 普通文件权限足以读取缓存。只有 `/proc/<pid>/mem` 读取被系统拒绝时，才使用本次会话已授权的 `sudo`；需要密码时通过终端隐藏输入或工具 stdin 提供，不放进命令参数、脚本、文档或仓库。不要降低系统 `ptrace_scope`。
4. 将密钥写到权限为 `0700` 的临时目录，密钥文件权限为 `0600`。使用脚本扫描与目标数据库盐匹配的密钥，并校验首页 HMAC。
5. 在内存中解密数据库和已提交 WAL，查询指定会话。微信的 `filehelper` 对应“文件传输助手”；消息表通常是 `Msg_<md5(username)>`。
6. 表情消息读取 `md5`、`len`、`width`、`height`，定位 `cache/<YYYY-MM>/Emoticon/<md5前两位>/<md5>`。缓存存在不等于已取得原图。
7. 若微信进程中保留原始图片字节，按消息长度读取候选文件并验证完整 MD5 后导出。未找到时明确说明需要在微信中重新打开目标表情，再重试；不要将截图裁剪、仅按修改时间匹配的缓存或未经校验的字节称为原始表情。
8. 检查导出文件格式、尺寸和动图帧数，提供文件路径与对应消息时间。删除临时密钥和工作文件；保留用户请求的导出文件。

```bash
# 使用同一个已安装依赖的 Python 解释器运行普通和 sudo 命令
python -m pip install pycryptodome zstandard
TASK_PYTHON=$(command -v python)
SCRIPT=/path/to/wechat_get_data/scripts/wechat_data.py
ACCOUNT="$HOME/Documents/xwechat_files/<account>"
PID=$(pgrep -x wechat)
WORK=$(mktemp -d)
chmod 700 "$WORK"

# 多个微信进程或账号时，先明确目标，再设置 PID 和 ACCOUNT
# 两条 --database 参数将扫描范围限制为表情库和指定消息分片
# 消息所在分片未知时可省略 --database，默认扫描表情库和所有 message_<数字>.db
sudo "$TASK_PYTHON" "$SCRIPT" scan-keys --pid "$PID" --account "$ACCOUNT" \
  --database db_storage/emoticon/emoticon.db \
  --database db_storage/message/message_1.db --output "$WORK/keys.json"

# 查询文件传输助手的表情消息；记录中的路径指向实际所在分片
"$TASK_PYTHON" "$SCRIPT" query --account "$ACCOUNT" --keys "$WORK/keys.json" \
  --chat filehelper --type 47 --limit 10 --output "$WORK/messages.json"

# 从查询结果选择一条记录，提供完整标识和长度，不能只根据截图猜测
sudo "$TASK_PYTHON" "$SCRIPT" extract --pid "$PID" --md5 <message-md5> \
  --length <message-length> --width <width> --height <height> \
  --output "$HOME/Downloads/目标表情.gif"

# 完成后删除临时密钥和查询结果
rm -rf -- "$WORK"
```

查询支持 `--since`、`--until`（Unix 秒或带时区的 ISO 时间）、`--contains`（文本消息关键词）、`--type` 和 `--limit`。只保存用户实际需要的查询结果；输出会包含指定范围内的聊天内容。

## 实现细节

- [scripts/wechat_data.py](scripts/wechat_data.py)：密钥扫描、只读消息查询、原始表情提取。
- [references/linux-wechat.md](references/linux-wechat.md)：读取数据库或排查失败时参考，包含已验证的 SQLCipher 格式、消息字段、表情缓存路径及恢复条件。
- 可选通过 `Pillow` 检查图片：`python -m pip install pillow`，再读取 `Image.open(path).size`、`format`、`n_frames`。

脚本不修改微信数据库，不暂停或重启微信，不保存进程内存转储。文件导出成功依赖目标原图仍在进程可读内存中；本方案未验证表情缓存的通用解密密钥，不能保证恢复所有历史表情。
