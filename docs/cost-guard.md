# 费用保护与到期关闭计费

## 三层规则

1. **Cloud Run 原生 Spend Cap：** USD 5 / 月，只限制 Cloud Run；以 Google 的估算原价口径为准，排除 credits，次月自动解除。
2. **整个项目的 USD 5 预算：** 预算事件经 Pub/Sub → Eventarc → Workflows，把 `lunatv` 设置为手动 0 实例。新账期每日 00:10（America/Los_Angeles）核对，仅恢复上月被此规则暂停的服务。手动暂停不接管，当月超额不恢复。
3. **到期终止：** `2027-10-22 00:00 Asia/Taipei` 起，工作流调用 Cloud Billing API，设置本项目 `billingAccountName: ""`，解除结算关联。不自动重新关联计费。

预算排除 credits，赠金不会扩大 USD 5 阈值。GCP 月度账期以美国太平洋时间划分，00:10 对应台北夏令时 15:10、冬令时 16:10，原生限额解除可能另有延迟。

**无法保证最终账单严格不超过 USD 5。** 费用入账、预算通知、平台执行都可能延迟。月度暂停只停止 Cloud Run 业务，镜像/秘密/构建源文件仍可能收费；到期关闭整个项目计费才覆盖该项目的保存资源。已发生费用仍可能补记。Upstash 独立保持原计划，不会随着 GCP 自动取消。

## 到期路径

- `jmgo-tv-expiry`：Asia/Taipei，`0 * 22 10 *`，默认截止日每小时尝试，首次对应 `2027-10-21T16:00:00Z`。
- `jmgo-tv-daily-reconcile`：America/Los_Angeles，`10 0 * * *`，同时检查到期。
- 预算事件也检查同一个截止时间，形成额外执行路径。
- 关闭计费前不暂停调度任务；如果调用失败，仍保留重试入口。
- 到期判断在读取 Cloud Run 服务之前，因此服务被删除不妨碍解绑。
- 成功解绑后不依赖进一步的云端调用；该项目的服务可能立即停用。

调度并非实时系统，无法保证恰好在零点完成。原生 Spend Cap 只限制 Cloud Run，不会主动关闭 Workflows / Scheduler。若人为停用相关 API、删除身份/任务、锁定项目结算关联或改变 IAM，到期动作可能失败。

## 权限限制

运行身份 `tv-cost-guard`：

- `run.services.get/update`：在 `lunatv` 服务 IAM 上授予。
- `iam.serviceAccounts.actAs`：仅对已有 `lunatv-runtime` 身份授予，Cloud Run 更新需要此权限。
- `run.operations.get`、`resourcemanager.projects.get`：仅在目标项目授予。
- **`resourcemanager.projects.deleteBillingAssignment`**：仅目标项目自定义角色，IAM 条件为 `request.time >= timestamp("2027-10-21T16:00:00Z")`。

触发身份 `tv-guard-trigger` 只有目标项目 `workflows.executions.create`；该专用项目应只用于此应用与保护工作流。没有服务账户私钥，没有项目 Owner/Editor，没有结算账户管理员权限，也没有重新开启计费的权限。

工作流和 IAM 都使用真实云端时间限制解绑。`dryRun: true` 的测试时间只影响演练，不会触发真实关闭；一个误加的 `expired` 标签也不能提前获得解绑权限。

## 核验与维护

```sh
python3 cloud/cost-guard/check.py       # 部署源匹配、计费只读状态、任务状态
python3 cloud/cost-guard/test_guard.py  # 18 个云端 dry-run 决策用例，无资源修改
```

实际提前解绑会影响所有项目资源，所以没有以真实关闭计费的方式测试到期动作。`test_guard.py` 的边界用例固定对应本仓库截止日期，修改截止时间时需同步改测试。

延长使用期限时：修改 `.local/cloud.json` 的 `expiry_utc`，检查测试边界，重新运行 `deploy.py`，再运行 `check.py`，确认工作流、IAM 条件和 Scheduler 同步更新。到期任务的 cron 不含年份，因此每年同日都会触发，但工作流和 IAM 的完整 UTC 日期会阻止提前解绑。

如果到期后手动恢复了计费，却没有先更新截止时间，下一次执行仍会关闭计费。不要只重开 Cloud Run 或只编辑定时任务。

官方依据：

- [项目计费停用与资源影响](https://docs.cloud.google.com/billing/docs/how-to/modify-project)
- [updateBillingInfo API](https://docs.cloud.google.com/billing/docs/reference/rest/v1/projects/updateBillingInfo)
- [Cloud Run Spend Cap](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps)
- [预算 Pub/Sub 通知](https://docs.cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications)
- [Cloud Run 手动缩放](https://docs.cloud.google.com/run/docs/configuring/services/manual-scaling)
