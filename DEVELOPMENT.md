# Development

## 常用命令

```bash
pnpm install
pnpm dev:api
pnpm dev:web
pnpm verify
```

## 测试策略

- 后端领域逻辑先写测试，再实现。
- 前端第一版以 `pnpm build:web` 和浏览器 smoke 验证为主。
- 修改 simulation schema 时必须同步更新 tests、README 输入示例和前端读取逻辑。

## 完成定义

- API 测试通过。
- 后端 lint 通过。
- Web build 通过。
- 本地浏览器能创建并运行一条 simulation。

