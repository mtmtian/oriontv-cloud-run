# 来源与修改说明

## LunaTV / MoonTV

- 上游：[MoonTechLab/LunaTV](https://github.com/MoonTechLab/LunaTV)
- 固定提交：`6c0428d1ae7a8322efa8031909ec77cac22fd866`
- 源码位置：`vendor/LunaTV/`，不包含 `.git` 历史、上游 GitHub Actions、依赖缓存和构建输出。
- 许可证：[CC BY-NC-SA 4.0 原文](vendor/LunaTV/LICENSE)。保留署名、非商业与相同方式共享条件；本仓库根目录 MIT 许可不覆盖该源码。
- 本次修改：`src/middleware.ts` 增加关闭媒体代理的开关；`src/app/api/cron/route.ts` 增加禁用 cron 开关；`start.js` 在禁用后台任务时跳过进程定时器；补充 `.gcloudignore`。
- LunaTV 的上述衍生改动沿用 CC BY-NC-SA 4.0。

## 客户端与节目来源

- [OrionTV](https://github.com/orion-lib/OrionTV)：外部客户端，仅提供接入文档，未复制客户端源码或 APK。
- [Guovin/iptv-api](https://github.com/Guovin/iptv-api)：示例引用公开生成的 IPv4 M3U，未复制采集器源码或节目媒体。
- 点播来源示例保留此次部署使用的公开 API 地址；没有复制视频、用户账号、访问凭据或私密订阅。

`cloud/` 与本仓库自写文档的原创部分采用根目录 MIT 许可；上述第三方内容维持各自许可证。此仓库与 Google、Upstash、OrionTV、LunaTV 官方没有隶属关系。
