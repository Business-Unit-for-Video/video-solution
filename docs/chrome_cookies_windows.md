如何从 Windows Chrome 导出 cookie 并用于 `yt-dlp` / 自动化

建议流程（不做 base64 编码，按原始 Netscape cookie.txt）：

1. 使用浏览器扩展例如 "EditThisCookie" 或 "Get cookies.txt" 导出当前站点的 cookies 为 `cookies.txt`（Netscape 格式）。
2. 将导出的 `cookies.txt` 放到工程根目录（或 CI secrets 指定的安全位置），并确保 `.gitignore` 已包含 `cookies.txt`。
3. 在下载命令中直接引用该文件，不做任何 base64 转换：

```bash
yt-dlp --cookies cookies.txt <VIDEO_URL>
```

注意事项：
- Windows Chrome 的 cookie 存储在加密的 SQLite 中，直接访问需要解密。导出扩展会把 cookie 转换为可供 `yt-dlp` 使用的文本格式。
- 在 CI 中建议不要把明文 cookie 放在仓库；使用 GitHub Actions secret 或者服务账号方式。
