# 构建指南 (Build Guide)

## 快速开始

### 1. 安装 PyInstaller

```bash
pip install pyinstaller
```

### 2. 打包主程序 (GUI)

```bash
pyinstaller --clean build.spec
```

产物: `dist/桌面自动化助手.exe` (约 64 MB)

### 3. 打包 MCP Server

```bash
pyinstaller --clean build_mcp.spec
```

产物: `dist/workflow-mcp-server.exe` (约 70 MB)

## 输出文件

| 文件 | 大小 | 用途 |
|------|------|------|
| `桌面自动化助手.exe` | 64 MB | GUI 客户端,双击直接运行 |
| `workflow-mcp-server.exe` | 70 MB | MCP Server,给 AI 客户端调用 |

## 分发

把 `dist/` 目录下的两个 exe 拷给用户即可,无需 Python 环境。

## 体积优化

当前每个 exe 约 64-70 MB,主要是 PySide6 + numpy 占大头。优化选项:

### A. 启用 UPX 压缩

下载 [UPX](https://github.com/upx/upx/releases),把 `upx.exe` 放到 PATH,PyInstaller 会自动调用。

可以减小 30-50% 体积。

### B. 排除未用的 PySide6 模块

修改 `build.spec` 的 `excludes`,但要小心不要排除运行时需要的。

### C. 用 `--onedir` 替代 `--onefile`

单目录模式启动快,但分发时要分发整个文件夹。

## 自定义图标

1. 准备 256x256 的 .ico 文件
2. 修改 `build.spec` 的 `icon='path/to/icon.ico'`
3. 重新打包

## 调试

打包时如果出现运行时 ImportError:

1. 用 `pyinstaller --clean build.spec` 清理后重新打包
2. 启动 exe 时加上 `--console` 临时改 console=True 看错误
3. 检查 `hiddenimports` 是否完整

## MCP Server 测试

启动 MCP server 后,用任意支持 MCP 的客户端连接:

```json
{
  "mcpServers": {
    "desktop-auto": {
      "command": "C:\\path\\to\\dist\\workflow-mcp-server.exe"
    }
  }
}
```

## 常见问题

### Q: 启动后白屏?
A: 检查 `samples/` 目录是否被正确打包。spec 文件里已经包含了。

### Q: 启动时 DLL 错误?
A: PySide6 / numpy 的 DLL 没找到。重新 `pip install` 对应包,然后重新打包。

### Q: 体积太大?
A: 见上方「体积优化」,或者考虑用 `nuitka` 替代 `pyinstaller`。
