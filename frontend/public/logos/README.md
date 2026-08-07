# 设备简图 / Logo 图库

本目录用于存放网络模型、拓扑等界面中的**设备简图与品牌 Logo**静态资源。

## 目录约定

| 子目录 | 用途 |
|--------|------|
| `devices/` | 按设备类型划分的简图（交换机、服务器、安全等） |
| `brands/` | 厂商 Logo（可选） |
| `common/` | 通用图标、占位图 |

## 命名建议

```
devices/
  switch-gigabit.svg
  switch-ten-gigabit.svg
  switch-core.svg
  switch-aggregation.svg
  server-1u.svg
  server-2u.svg
  server-4u.svg
  security-1u.svg
  security-2u.svg
  router.svg
  load-balancer.svg
  software.svg
```

## 引用方式

静态文件通过站点根路径访问（Vite `public`）：

```text
/logos/devices/switch-gigabit.svg
/logos/brands/huawei.png
```

代码中请使用 `frontend/src/utils/deviceLogoPaths.ts` 中的路径辅助函数，避免硬编码散落。

## 格式

- 优先 **SVG**（矢量、可缩放）
- 位图可用 **PNG / WebP**，建议边长 ≥ 128px
- 单文件建议 < 200KB
