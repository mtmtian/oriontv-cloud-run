# 部署

这是专用家庭电视项目的配方。新建一个单独的 GCP 项目并关联自己的结算账户，不要用同时运行其他业务的项目，因为固定到期动作会关闭整个目标项目计费。已验证配置日期为 2026-10-24。

## 1. 准备非秘密参数

在仓库根目录执行：

```sh
mkdir -p .local
cp cloud/config.example.json .local/cloud.json
```

编辑 `.local/cloud.json` 的 `project_id` 和 `billing_account`。默认地区 `asia-east1`，额度 USD 5，截止时间 `2027-10-21T16:00:00Z`。需要其他截止时间时必须同时核对 [费用保护说明](cost-guard.md)。文件不要放密码、token 或订阅地址。

使用 `gcloud auth login` 登录拥有目标项目管理权限、结算预算管理权限的账号。脚本每次显式指定项目，不修改 CLI 全局默认项目。没有下载服务账户 JSON 私钥的步骤。

## 2. 准备 Upstash 和秘密值

在 [Upstash 控制台](https://console.upstash.com/) 创建 Redis，选择 Free 计划，复制 **REST URL / REST TOKEN**。这是 REST 客户端所需的两项，不是传统 Redis TCP 连接密码。

```sh
python3 cloud/bootstrap.py
python3 cloud/secrets.py
```

后者用不回显的提示读取管理员密码、Upstash 两项和电视用户密码。秘密值通过标准输入交给 Secret Manager，不写入本地文件、不进入命令行参数。已有启用版本会保留，不自动轮换密码。原有 Upstash 数据库的账号与数据不会被迁移。

运行身份只获得三个运行所需秘密的读取权；构建身份只有镜像仓库写入、构建桶读取与日志写入。四个 Secret Manager 条目的名字固定为：

- `lunatv-admin-password`
- `lunatv-upstash-url`
- `lunatv-upstash-token`
- `lunatv-tv-password`（用于初始化普通电视用户，不提供给运行容器）

## 3. 构建与部署

```sh
python3 cloud/deploy_service.py
```

它将本仓库的 `vendor/LunaTV` 交给 Cloud Build，在私有 Artifact Registry `home-tv` 保存镜像，用构建结果的 digest 部署，记录保存在 `.local/service.json`。构建和源代码存储可能收费；首次部署过程不是免费的保证。

Cloud Run 入口允许公网请求，因为 OrionTV 不使用 Google IAM 登录；LunaTV 自己验证账号密码。保留 `DISABLE_VIDEO_PROXY=true`、`DISABLE_BACKGROUND_JOBS=true`，否则视频中转/后台任务会改变费用模型。未来更新依赖或上游源码前，请独立审查并测试。

## 4. 费用保护

```sh
python3 cloud/cost-guard/budgets.py
python3 cloud/cost-guard/deploy.py
python3 cloud/cost-guard/test_guard.py
python3 cloud/cost-guard/check.py
```

创建两条仅过滤当前项目的 USD 5 月预算：整个项目的 Pub/Sub 通知预算，以及 Cloud Run 原生 Spend Cap。原生限额要求 50%/80%/100% 邮件通知，接收者为 Google 配置的项目/结算管理员。若账号尚不支持原生 Spend Cap，脚本会报错，不能把普通预算当成硬上限。

保护脚本依赖已存在的 `lunatv` 服务、`lunatv-runtime` 身份和该项目的有效计费。新项目的服务身份/IAM 传播可能需要等待，失败后检查错误再重跑；不应为了通过错误给运行身份 Owner/Editor。

预算 ID、工作流渲染结果和回执保存到 `.local/cost-guard/`。工作流会严格检查预算 ID 和账期。原部署的账户与资源 ID 已从仓库移除；不要把别人的预算 ID 填进模板。

## 5. 导入来源和电视账号

```sh
cp cloud/sources.example.json .local/sources.json
# 根据需要编辑 .local/sources.json
python3 cloud/configure_service.py
```

示例包含量子、光速、如意、无尽、iKun 五个公开点播 API 与 Guovin 公共直播列表。它们属于第三方，内容和可用性不由本仓库控制；不是本仓库托管的视频库。上面的默认导入动作会替换后台的来源配置，先保留自己原有配置。

已有部署补充来源时使用增量模式：

```sh
python3 cloud/configure_service.py --add-sources cloud/sources.example.json
```

增量模式只调用后台的单源添加接口：相同 key、相同 API 的源跳过，不改变原有名称、禁用状态或顺序；相同 key 指向不同 API 时在写入前报错。直播、订阅、用户、收藏及进度不由此模式修改。批次不是事务；中途失败时已添加的源保留，重新核对后再次执行会跳过它们。新增源不会扩大已有用户/用户组的显式源权限白名单，需要管理员按实际需求另行授权。

`configure_service.py` 会从 Cloud Run 查询并验证后端地址，然后在内存中用管理员登录，导入来源，并在缺少时创建普通用户 `projector`。已有用户不会被重置密码。它不会打印来源正文、密码或登录 cookie。电视端设置见 [OrionTV 接入](oriontv.md)。

私密源或订阅只放 `.local/sources.json`；不要改公开示例后直接提交。脚本不会抓取或打包影片文件。

## 恢复部署

源代码和配置模板不能代替数据库备份。收藏、播放进度在 Upstash，秘密值在自己的 Secret Manager。停止计费后 Google 可能清理 GCP 资源，若重新部署，应重新启用/关联计费、重新创建缺失资源和秘密，并明确修改工作流与 IAM 的截止时间；否则恢复后会再次被关闭。

先核对 Upstash 仍存在，再运行上述初始化与部署步骤。没有默认自动恢复项目计费的脚本。构建桶和镜像可在自己确认无须恢复旧版本后清理，但不作为本次到期动作的前提。
