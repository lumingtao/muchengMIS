import { Button, Card, Tag } from "antd";
import { AnyRecord } from "../../api";
import { LegacyView } from "./navigation";

export function LegacyOverview({ source, cache, batch, onNavigate }: {
  source?: AnyRecord | null; cache?: AnyRecord; batch?: AnyRecord;
  onNavigate: (view: LegacyView) => void;
}) {
  const next = !source ? "legacySource" : !Number(cache?.total) ? "legacyCache" : "legacySync";
  const nextLabels = { legacySource: "配置来源连接", legacyCache: "拉取来源数据", legacySync: "进入同步审核" };
  return <>
    <Card className="legacy-intro">
      <div className="legacy-heading-row">
        <div><Tag color="blue">无锡来源 · 单向同步</Tag><h2>按步骤整理，再确认导入</h2><p>拉取先进入本地暂存；复核后勾选同步，在修工单可继续接管。</p></div>
        <Button type="primary" size="large" onClick={() => onNavigate(next)}>{nextLabels[next]}</Button>
      </div>
      <div className="legacy-metrics">
        <div><span>来源连接</span><strong>{source ? "已配置" : "待配置"}</strong></div>
        <div><span>本地暂存</span><strong>{Number(cache?.total || 0).toLocaleString()}<small> 条</small></strong></div>
        <div><span>已排除 / 来源缺失</span><strong>{String(cache?.excluded || 0)} / {String(cache?.missing || 0)}</strong></div>
        <div><span>当前批次记录</span><strong>{Number(batch?.total || 0).toLocaleString()}<small> 条</small></strong></div>
      </div>
    </Card>
    <div className="legacy-flow-grid">
      {([
        ["legacyCache", "01", "整理暂存数据", "首次拉取或日常增量，搜索并排除暂不导入的账单。"],
        ["legacySync", "02", "预览与同步", "核对差异；遇到未知员工或状态时，先调整映射再预览。"],
        ["legacyRecords", "03", "查询与接管", "查看导入结果、历史金额，确认在修工单的接管信息。"],
      ] as const).map(([view, number, title, note]) => <button className="legacy-flow-card" type="button" key={view} onClick={() => onNavigate(view)}>
        <span className="legacy-step-number">{number}</span><strong>{title}</strong><span>{note}</span><b>进入 →</b>
      </button>)}
    </div>
  </>;
}
