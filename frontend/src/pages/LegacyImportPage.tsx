import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Checkbox, Descriptions, Form, Input, InputNumber, Modal, Progress, Select, Space, Spin, Table, Tag } from "antd";
import { AnyRecord, api } from "../api";
import { LegacyOverview } from "./legacy/LegacyOverview";
import { LegacyView } from "./legacy/navigation";
import "./legacy/legacy.css";

type Props = { notify: (message: string, error?: boolean) => void; openOrderDetail?: (row: AnyRecord) => void };
const labels: Record<string, string> = { new: "新增", update: "更新", unchanged: "无变化", review: "待确认", invalid: "身份异常", taken_changed: "接管后变化", missing: "来源缺失", pending: "待执行", blocked: "待处理", success: "成功", failed: "失败", queued: "等待读取", reading: "读取中", preview: "待执行预览", queued_execute: "等待执行", executing: "执行中", partial: "部分完成", completed: "完成", interrupted: "已中断", active: "接管后继续办理", history: "仅作历史查询", unknown: "待核实后导入", following: "跟随老系统", taken: "新系统已接管" };
export const displayLegacyValue = (value: unknown) => value === null ? "NULL" : value === undefined ? "—" : value === "" ? "（空字符串）" : typeof value === "object" ? JSON.stringify(value) : String(value);
const display = displayLegacyValue;
const send = (path: string, data: unknown = {}, method = "POST") => api<AnyRecord>(`/api/legacy-import${path}`, { method, body: JSON.stringify(data) });

function useLegacyAction(notify: Props["notify"]) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  async function action(fn: () => Promise<unknown>, message: string) {
    setBusy(true);
    try { await fn(); notify(message); await qc.invalidateQueries({ queryKey: ["legacy"] }); }
    catch (error) { notify(error instanceof Error ? error.message : "操作失败", true); }
    finally { setBusy(false); }
  }
  return { busy, action };
}

export function LegacyImportPage({ notify, openOrderDetail, section = "legacyImport", onNavigate }: Props & { section?: LegacyView; onNavigate?: (view: LegacyView) => void }) {
  const [localSection, setLocalSection] = useState(section);
  const currentSection = onNavigate ? section : localSection;
  const navigate = onNavigate || setLocalSection;
  const me = useQuery({ queryKey: ["me", "legacy"], queryFn: () => api<AnyRecord>("/api/me") });
  const admin = ["admin", "boss"].includes(String(me.data?.role));
  const adminPage = admin && currentSection !== "legacyRecords";
  const source = useQuery({ queryKey: ["legacy", "source"], queryFn: () => api<AnyRecord | null>("/api/legacy-import/source"), enabled: adminPage, refetchInterval: 4000 });
  const batches = useQuery({ queryKey: ["legacy", "batches"], queryFn: () => api<AnyRecord[]>("/api/legacy-import/batches"), enabled: adminPage && ["legacyImport", "legacySync", "legacyMappings"].includes(currentSection), refetchInterval: 4000 });
  const [config] = Form.useForm();
  const [filters] = Form.useForm();
  const restoredFilterBatch = useRef("");
  const { busy, action } = useLegacyAction(notify);
  const [batchId, setBatchId] = useState("");
  useEffect(() => { if (!batchId && batches.data?.length) setBatchId(String(batches.data[0].batch_id)); }, [batchId, batches.data]);
  const cacheStatus = useQuery({ queryKey: ['legacy', 'cache-status'], queryFn: () => api<AnyRecord>('/api/legacy-import/cache/status'), enabled: adminPage && Boolean(source.data), refetchInterval: 2000 });
  const [page, setPage] = useState(1);
  const [selectedItems, setSelectedItems] = useState<React.Key[]>([]);
  useEffect(() => { setSelectedItems([]); }, [batchId]);
  const [item, setItem] = useState<AnyRecord | null>(null);
  useEffect(() => {
    setItem(null);
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [currentSection]);
  const [engineerMaps, setEngineerMaps] = useState<Record<string, string>>({});
  const [stateMaps, setStateMaps] = useState<Record<string, { classification: string; status: string }>>({});
  const employees = useQuery({ queryKey: ["legacy", "employees"], queryFn: () => api<AnyRecord[]>("/api/dispatch-engineers"), enabled: admin && currentSection === "legacyMappings" });
  const [candidateSearch, setCandidateSearch] = useState("");
  const [candidate, setCandidate] = useState<number>();
  const batch = useQuery({ queryKey: ["legacy", "batch", batchId], queryFn: () => api<AnyRecord>(`/api/legacy-import/batches/${batchId}`), enabled: adminPage && ["legacyImport", "legacySync", "legacyMappings"].includes(currentSection) && Boolean(batchId), refetchInterval: 2000 });
  const items = useQuery({ queryKey: ["legacy", "items", batchId, page], queryFn: () => api<AnyRecord[]>(`/api/legacy-import/batches/${batchId}/items?offset=${(page - 1) * 50}&limit=50`), enabled: admin && currentSection === "legacySync" && Boolean(batchId), refetchInterval: 3000 });
  const candidates = useQuery({ queryKey: ["legacy", "candidates", candidateSearch], queryFn: () => api<AnyRecord[]>(`/api/legacy-import/candidates?q=${encodeURIComponent(candidateSearch)}`), enabled: admin && currentSection === "legacySync" && Boolean(item) });
  useEffect(() => {
    if (currentSection !== "legacySync" || !batch.data || restoredFilterBatch.current === batchId) return;
    const saved = (batch.data.filters || {}) as AnyRecord;
    filters.setFieldsValue({ ids: Array.isArray(saved.ids) ? saved.ids.join(",") : "", date_from: saved.date_from || "", date_to: saved.date_to || "" });
    restoredFilterBatch.current = batchId;
  }, [currentSection, batch.data, batchId, filters]);
  useEffect(() => {
    if (source.data) {
      const mappings = (source.data.mappings || {}) as AnyRecord;
      setEngineerMaps((mappings.engineers || {}) as Record<string, string>);
      setStateMaps((mappings.states || {}) as Record<string, { classification: string; status: string }>);
    }
  }, [source.data?.version]);
  useEffect(() => {
    if (currentSection === "legacySource" && source.data && !config.isFieldsTouched()) {
      config.setFieldsValue({ base_url: source.data.base_url, username: source.data.username });
    }
  }, [currentSection, source.data, config]);
  const operationBusy = busy || Boolean(source.data?.busy) || Boolean(cacheStatus.data?.busy);
  const batchStatus = String(batch.data?.status || "");
  const profile = (batch.data?.profile || {}) as AnyRecord;
  const engineerNames = Array.from(new Set([...Object.keys((profile.engineers || {}) as AnyRecord), ...Object.keys(engineerMaps)])).filter(Boolean);
  const stateKeys = Array.from(new Set([...Object.keys((profile.state_combinations || {}) as AnyRecord), ...Object.keys(stateMaps)]));
  const [locallyStale, setPreviewStale] = useState(false);
  const previewStale = locallyStale
    || (batch.data?.source_version != null && source.data?.version != null && batch.data.source_version !== source.data.version)
    || (profile.cache_revision != null && cacheStatus.data?.revision != null && profile.cache_revision !== cacheStatus.data.revision);
  const batchPicker = <div className="legacy-toolbar">
    <Select className="legacy-batch-select" aria-label="选择同步批次" placeholder="选择已有同步批次" value={batchId || undefined} options={(batches.data || []).map(b => ({ value: String(b.batch_id), label: `${b.created_at} · ${String(b.batch_id).slice(0, 8)} · ${labels[String(b.status)] || b.status}` }))} onChange={id => { setBatchId(id); setPage(1); }} />
    {batchId && <Tag>{labels[batchStatus] || batchStatus || "正在读取"}</Tag>}
  </div>;
  const saveMappings = (continueToPreview: boolean) => action(async () => {
    await send("/mappings", { engineers: engineerMaps, states: stateMaps }, "PUT");
    setPreviewStale(true); setSelectedItems([]);
    if (continueToPreview) navigate("legacySync");
  }, "映射已保存，请重新生成预览");
  if (me.isPending) return <Spin aria-label="正在读取导入权限" />;
  if (me.error) return <Alert type="error" title={me.error.message} />;
  if (!admin || currentSection === "legacyRecords") return <div className="legacy-workspace">
    <LegacyRecords notify={notify} openOrderDetail={openOrderDetail} />
  </div>;
  return <div className="legacy-workspace">
    {source.error && currentSection !== "legacySource" && <Alert type="error" title={source.error.message} />}
    {currentSection !== "legacySource" && source.isSuccess && !source.data && <Alert type="info" showIcon title="首次使用，请先配置来源连接" action={<Button onClick={() => navigate("legacySource")}>前往连接设置</Button>} />}
    {currentSection === "legacyImport" && <LegacyOverview source={source.data} cache={cacheStatus.data} batch={batch.data} onNavigate={navigate} />}
    {currentSection === "legacyImport" && <Alert type="info" showIcon title="未接管工单跟随老系统" description="历史金额单独保存，同步不生成收付款和库存流水。确认接管后，由新系统维护该工单。" />}
    {currentSection === "legacyImport" && <Card title="任务与进度" extra={<Space wrap><Button disabled={!source.data || operationBusy} onClick={() => void action(() => send("/attachments/retry"), "附件重试已提交")}>重试图片复制</Button><Button disabled={busy} onClick={() => void action(async () => undefined, '任务状态已刷新')}>刷新任务状态</Button></Space>}>
      <Space orientation="vertical" style={{ width: '100%' }}>
        <LegacyTaskProgress title="最近暂存拉取" task={cacheStatus.data?.job as AnyRecord | undefined} kind="fetch" />
        <LegacyTaskProgress title="当前预览 / 同步" task={batch.data || (batchId ? { batch_id: batchId, status: 'queued' } : undefined)} kind="batch" />
        {(cacheStatus.error || batches.error || batch.error) && <Alert type="error" title={(cacheStatus.error || batches.error || batch.error)?.message} />}
        <Table<AnyRecord> aria-label="最近同步任务" size="small" rowKey="batch_id" scroll={{ x: 700 }} pagination={{ pageSize: 5, showSizeChanger: false }} dataSource={batches.data || []} columns={[
          { title: '创建时间', dataIndex: 'created_at' }, { title: '任务编号', dataIndex: 'batch_id', render: value => String(value).slice(0, 8) },
          { title: '状态', dataIndex: 'status', render: value => labels[String(value)] || value }, { title: '失败原因', dataIndex: 'error' },
          { title: '操作', render: (_, row) => <Button onClick={() => { setBatchId(String(row.batch_id)); setPage(1); navigate("legacySync"); }}>查看任务</Button> },
        ]} />
      </Space>
    </Card>}
    {currentSection === "legacySource" && <Card title="连接设置 · 无锡来源">
          {source.error && <Alert type="error" title={source.error.message} />}
          <Form className="legacy-source-form" form={config} layout="vertical" initialValues={{ base_url: source.data?.base_url || "https://app.muchen668.top", username: source.data?.username || "muchen888" }} onFinish={values => void action(async () => { await send("/source", values, "PUT"); config.setFieldValue("password", ""); }, "连接设置已保存")}>
            <Form.Item name="base_url" label="API 地址" rules={[{ required: true }]}><Input disabled={operationBusy} /></Form.Item>
            <Form.Item name="username" label="账号" rules={[{ required: true }]}><Input disabled={operationBusy} autoComplete="username" /></Form.Item>
            <Form.Item name="password" label="密码（已配置时留空保留原密码）"><Input.Password disabled={operationBusy} autoComplete="new-password" /></Form.Item>
            <Space><Button type="primary" htmlType="submit" disabled={operationBusy}>保存连接</Button><Button disabled={!source.data || operationBusy} onClick={() => void action(async () => { const result = await send("/source/test"); notify(`连接成功，账单 ${result.count} 条，字段 ${(result.fields as unknown[]).length} 个`); }, "连接检查完成")}>测试连接</Button></Space>
          </Form>
          <div className="legacy-page-actions"><Button disabled={!source.data} onClick={() => navigate("legacyCache")}>下一步：拉取与整理数据 →</Button></div>
        </Card>}
    {currentSection === "legacyCache" && <>
      <LegacyCachePanel notify={notify} enabled={Boolean(source.data)} busy={operationBusy} />
      <div className="legacy-toolbar"><span>整理完毕后，从未排除的记录中生成预览。</span><Button type="primary" disabled={!Number(cacheStatus.data?.total) || operationBusy} onClick={() => navigate("legacySync")}>下一步：生成同步预览 →</Button></div>
    </>}
    {currentSection === "legacySync" && <>
      {!Number(cacheStatus.data?.total) && !cacheStatus.isLoading && <Alert type="info" showIcon title="本地暂无暂存数据，请先拉取来源账单" action={<Button onClick={() => navigate("legacyCache")}>前往数据暂存</Button>} />}
        <Card title="生成同步预览" extra={<Button onClick={() => navigate("legacyCache")}>返回暂存整理</Button>}>
          <p>日期与旧账单 ID 均留空时，预览全部未排除记录。生成预览后，核对差异并勾选要同步的记录。</p>
          <Form className="legacy-filter-form" form={filters} layout="vertical" onFinish={values => void action(async () => {
            const ids = String(values.ids || "").split(/[,，\n]/).map(v => v.trim()).filter(Boolean);
            const result = await send("/preview", { ids, date_from: values.date_from || "", date_to: values.date_to || "" });
            setBatchId(String(result.batch_id)); setPage(1); setPreviewStale(false);
          }, "本地预览已创建，不重新拉取全库")}>
            <Form.Item name="date_from" label="开始日期"><Input type="date" /></Form.Item><Form.Item name="date_to" label="结束日期" dependencies={["date_from"]} rules={[({ getFieldValue }) => ({ validator: (_, value) => !value || !getFieldValue("date_from") || value >= getFieldValue("date_from") ? Promise.resolve() : Promise.reject(new Error("结束日期应晚于或等于开始日期")) })]}><Input type="date" /></Form.Item>
            <Form.Item name="ids" label="旧账单 ID"><Input placeholder="逗号分隔；留空读取全部" /></Form.Item>
            <Button htmlType="submit" type="primary" disabled={!source.data || operationBusy || !Number(cacheStatus.data?.total)}>从本地生成预览</Button>
          </Form>
        </Card>
        <Card title="批次审核" extra={<Button onClick={() => navigate("legacyMappings")}>调整映射规则</Button>}>
          {batchPicker}
          <div style={{ marginTop: 16 }}><LegacyTaskProgress title="当前预览 / 同步" task={batch.data || (batchId ? { batch_id: batchId, status: "queued" } : undefined)} kind="batch" /></div>
          {previewStale && <Alert type="warning" showIcon title="暂存数据、配置或关联已变化，请重新生成预览后再同步" style={{ marginTop: 12 }} />}
          {batch.data && <p>记录 {String(batch.data.total)} 条；{((batch.data.counts || []) as AnyRecord[]).map(c => `${labels[String(c.action)]} / ${labels[String(c.result)]}: ${c.count}`).join("；")}</p>}
          {batchStatus === "reading" && <p>正在读取并复核来源：{String(profile.scan_read || 0)} / {String(profile.source_count || "…")} 条；复核时进度会重新计数。</p>}
          {(batch.error || items.error || cacheStatus.error) && <Alert type="error" title={(batch.error || items.error || cacheStatus.error)?.message} />}
          <Table<AnyRecord> aria-label="同步预览记录" rowKey="item_id" locale={{ emptyText: batchId ? "此批次暂无记录，请检查筛选条件或等待预览完成" : "先从本地生成预览，再核对记录" }} rowSelection={{ selectedRowKeys: selectedItems, preserveSelectedRowKeys: true, onChange: setSelectedItems, getCheckboxProps: row => ({ disabled: previewStale || operationBusy || batchStatus !== "preview" || ["invalid", "review"].includes(String(row.action)) }) }} loading={items.isLoading} dataSource={items.data || []} scroll={{ x: 900 }} pagination={{ current: page, pageSize: 50, total: Number(batch.data?.total || 0), showSizeChanger: false, onChange: setPage }} columns={[
            { title: "旧 ID", dataIndex: "source_id_raw" }, { title: "差异", dataIndex: "action", render: v => labels[String(v)] || v }, { title: "结果", dataIndex: "result", render: v => labels[String(v)] || v }, { title: "说明", dataIndex: "reason" },
            { title: "操作", render: (_, row) => <Button onClick={() => void action(async () => { setItem(await api<AnyRecord>(`/api/legacy-import/items/${row.item_id}`)); setCandidate(undefined); setCandidateSearch(""); }, "字段详情已读取")}>全部字段 / 关联</Button> },
          ]} />
          {Boolean(batch.data?.profile) && <details><summary>数据核验结果（状态、员工、重复身份及异常）</summary><pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(batch.data?.profile, null, 2)}</pre></details>}
        </Card>
        <div className="legacy-toolbar legacy-selection-bar">
          <span>{batchStatus === "preview" ? `跨页已选 ${selectedItems.length} 条，仅同步勾选记录` : "执行结果与失败原因显示在当前批次中"}</span>
          <Space wrap><Button type="primary" disabled={previewStale || operationBusy || !["preview", "partial", "interrupted", "failed"].includes(batchStatus) || (batchStatus === "preview" && !selectedItems.length)} onClick={() => Modal.confirm({ title: batchStatus === "preview" ? "确认同步选中记录到订单系统？" : "重试本批次失败记录？", content: batchStatus === "preview" ? `已选 ${selectedItems.length} 条，将备份新库并复核这些账单后写入。未勾选记录留在暂存库。` : "仅重试此批次上次已选的失败记录，不增加同步范围。", onOk: () => action(() => send(`/batches/${batchId}/${batchStatus === "preview" ? "execute" : "retry"}`, { item_ids: selectedItems }), "同步任务已提交") })}>{batchStatus === "preview" ? `确认同步（${selectedItems.length} 条）` : "重试失败记录"}</Button><Button onClick={() => navigate("legacyRecords")}>查看导入记录 →</Button></Space>
        </div>
    </>}
    {currentSection === "legacyMappings" && <Card title="员工与状态映射">
          {batchPicker}
          {(batches.error || batch.error || employees.error) && <Alert type="error" title={(batches.error || batch.error || employees.error)?.message} />}
          {!batchId && <Alert type="info" showIcon title="先生成一次预览，识别来源工程师与状态组合" action={<Button onClick={() => navigate("legacySync")}>去生成预览</Button>} />}
          <p>先生成预览，再配置工程师对应关系，以及每种老系统标记的后续处理方式和导入时业务状态。未手动设置时由系统自动判断，具体结果在同步审核中查看；修改后需保存并重新生成预览。</p>
          <p>接管后继续办理：确认接管后处理后续业务；仅作历史查询：保留查询与历史金额统计，不进入日常待办；待核实后导入：先核实处理方式，再确认同步。</p>
          <LegacyEngineerMappings names={engineerNames} mappings={engineerMaps} employees={employees.data || []} onChange={(name, username) => setEngineerMaps(prev => { const next = { ...prev }; if (username) next[name] = username; else delete next[name]; return next; })} />
          <Table<{ key: string }> rowKey="key" size="small" style={{ marginTop: 12 }} pagination={{ pageSize: 10 }} scroll={{ x: 750 }} dataSource={stateKeys.map(key => ({ key }))} columns={[
            { title: "老备注 / 付款标记", dataIndex: "key", render: key => String(key).replace("|", " / ") },
            { title: "后续处理方式", render: (_, r) => <Select style={{ width: 190 }} allowClear placeholder="自动判断" value={stateMaps[r.key]?.classification} options={[{ value: "active", label: labels.active }, { value: "history", label: labels.history }, { value: "unknown", label: labels.unknown }]} onChange={classification => setStateMaps(prev => { const next = { ...prev }; if (classification) next[r.key] = { classification, status: next[r.key]?.status || "已开单" }; else delete next[r.key]; return next; })} /> },
            { title: "导入时业务状态", render: (_, r) => <Select style={{ width: 170 }} placeholder="自动判断" disabled={!stateMaps[r.key]} value={stateMaps[r.key]?.status} options={["已开单", "检测中", "已报价", "处理中", "待交付", "已交付", "已结单", "已作废"].map(status => ({ value: status, label: status }))} onChange={status => setStateMaps(prev => ({ ...prev, [r.key]: { ...prev[r.key], status } }))} /> },
          ]} />
          <Space className="legacy-page-actions" wrap>
            <Button type="primary" disabled={!source.data || operationBusy} onClick={() => void saveMappings(false)}>保存映射</Button>
            <Button disabled={!source.data || operationBusy} onClick={() => void saveMappings(true)}>保存并去重新预览 →</Button>
          </Space>
        </Card>}
    <Modal open={Boolean(item)} title={`旧账单 ${String(item?.source_id_raw || "")} · 完整字段与差异`} width={960} footer={null} onCancel={() => setItem(null)}>
      <Table<AnyRecord> size="small" rowKey="field" pagination={false} dataSource={Object.entries((item?.raw || {}) as AnyRecord).map(([field, value]) => ({ field, value, previous: ((item?.previous || {}) as AnyRecord)[field] }))} columns={[
        { title: "字段", dataIndex: "field" }, { title: "上次来源值", dataIndex: "previous", render: display }, { title: "当前来源值", dataIndex: "value", render: display },
      ]} />
      {item && ["new", "review"].includes(String(item.action)) && !item.repair_order_id && <Card title="关联已有新系统工单" style={{ marginTop: 16 }}>
        <Alert type="info" title="关联后由新系统接管，保留现有业务数据。关联不会覆盖既有流水和项目。" />
        <Input.Search style={{ margin: "12px 0" }} placeholder="按新工单号或客户搜索" onSearch={setCandidateSearch} />
        <Select style={{ width: "100%" }} value={candidate} onChange={setCandidate} options={(candidates.data || []).map(c => ({ value: Number(c.repair_order_id), label: `${c.order_no} · ${c.customer_name} · ${c.status}` }))} />
        <Button disabled={!candidate || busy} style={{ marginTop: 12 }} onClick={() => Modal.confirm({ title: "确认两条记录为同一维修业务？", content: "将建立唯一对应关系，并保持新系统接管。", onOk: () => action(async () => { const selected = candidates.data?.find(c => Number(c.repair_order_id) === candidate); await send(`/items/${item.item_id}/associate`, selected); setItem(null); setPreviewStale(true); setSelectedItems([]); }, "已关联，请重新预览") })}>确认关联并保持接管</Button>
      </Card>}
    </Modal>
  </div>;
}

export function LegacyTaskProgress({ title, task, kind }: { title: string; task?: AnyRecord; kind: 'fetch' | 'batch' }) {
  if (!task?.status) return <p>{title}：尚无任务</p>;
  const status = String(task.status);
  const active = ['queued', 'reading', 'queued_execute', 'executing'].includes(status);
  const failed = ['failed', 'interrupted', 'partial'].includes(status);
  const result = (task.result || {}) as AnyRecord;
  const progress = (task.progress || {}) as AnyRecord;
  const done = Number(kind === 'fetch' ? result.received || 0 : progress.done || 0);
  const total = kind === 'fetch' ? result.total : progress.total;
  const measuring = kind === 'fetch' || ['executing', 'completed', 'partial'].includes(status);
  const percent = total && measuring ? Math.min(100, Math.floor(done / Number(total) * 100)) : undefined;
  const phase = kind === 'fetch' ? String(result.phase || (active ? '等待后台读取' : labels[status])) : ({ queued: '等待生成本地预览', reading: '正在筛选本地暂存记录并计算差异', preview: '预览已完成，请勾选记录后确认同步', queued_execute: '准备连接复核与备份', executing: '复核来源并逐条同步；记录处理后继续复制附件', completed: '同步完成', partial: '部分完成，请查看失败或待处理记录' } as Record<string, string>)[status] || labels[status];
  return <div role="status" aria-label={title} style={{ padding: 12, border: '1px solid #d9d9d9', borderRadius: 8 }}>
    <Space wrap><strong>{title}</strong><Tag color={failed ? 'red' : active ? 'blue' : 'green'}>{labels[status] || status}</Tag>{active && <Spin size="small" />}<span>任务 {String(task.job_id || task.batch_id || '').slice(0, 8)}</span><span>{String(task.created_at || '')}</span></Space>
    <p>{phase}</p>
    {percent !== undefined && <Progress percent={percent} status={failed ? 'exception' : active ? 'active' : 'normal'} />}
    {kind === 'fetch' ? <p>已保存 {done}{total != null ? ` / ${total}` : ''} 条；新增 {String(result.new || 0)}，变化 {String(result.changed || 0)}，无变化 {String(result.unchanged || 0)}。</p>
      : measuring && <p>已处理 {done} / {String(total || 0)} 条；{((task.counts || []) as AnyRecord[]).map(row => `${labels[String(row.result)] || row.result} ${row.count}`).join('；')}</p>}
    {Boolean(task.error) && <Alert type="error" title={String(task.error)} />}
    {active && <span>后台执行中，每 2–3 秒自动更新；刷新页面后仍可查看任务。</span>}
  </div>;
}

export function LegacyCachePanel({ notify, enabled, busy }: { notify: Props['notify']; enabled: boolean; busy: boolean }) {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ['legacy', 'cache-status'], queryFn: () => api<AnyRecord>('/api/legacy-import/cache/status'), enabled, refetchInterval: 3000 });
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [includeExcluded, setIncludeExcluded] = useState(false);
  const [editing, setEditing] = useState<AnyRecord | null>(null);
  const [note, setNote] = useState('');
  const records = useQuery({ queryKey: ['legacy', 'cache-records', q, page, includeExcluded], queryFn: () => api<AnyRecord>(`/api/legacy-import/cache/records?q=${encodeURIComponent(q)}&offset=${(page - 1) * 50}&include_excluded=${includeExcluded}`), enabled, refetchInterval: 5000 });
  const { busy: working, action } = useLegacyAction(notify);
  const disabled = busy || working || Boolean(status.data?.busy);
  const job = (status.data?.job || {}) as AnyRecord;
  const submitFetch = (mode: string) => action(async () => {
    const created = await send('/cache/fetch', { mode });
    qc.setQueryData(['legacy', 'cache-status'], (previous: AnyRecord | undefined) => ({ ...previous, busy: true, job: { job_id: created.job_id, status: 'queued', result: {}, created_at: '刚刚提交' } }));
  }, mode === 'full' ? '全量核对已提交' : '暂存拉取任务已提交');
  return <Card title="本地暂存库 · 与订单系统隔离">
    <Alert type="info" title="拉取只保存到本地，不创建工单或财务库存记录" description="首次初始化读取全库；以后增量读取新增和有更新时间的账单，每次额外轮换核验最多 500 条旧记录。筛选、备注与排除在本地完成；确认同步前只复核选中的账单。未维护更新时间的历史修改可能延迟发现，可手动全量核对。" />
    <p>本地 {String(status.data?.total || 0)} 条；已排除 {String(status.data?.excluded || 0)} 条；来源缺失 {String(status.data?.missing || 0)} 条；最近拉取 {String(status.data?.fetched_at || '尚未初始化')}</p>
    <Space wrap>
      <Button type="primary" loading={working} disabled={!enabled || disabled} onClick={() => void submitFetch('incremental')}>{status.data?.initialized ? '增量拉取到本地' : '首次拉取到本地'}</Button>
      <Button disabled={!enabled || disabled} onClick={() => Modal.confirm({ title: '手动全量核对本地暂存库？', content: '重新核对全部来源记录，仍只更新暂存库，不同步到订单系统。', onOk: () => submitFetch('full') })}>手动全量核对</Button>
      <Input.Search aria-label="搜索暂存记录" placeholder="旧 ID、客户、机型、工程师" onSearch={value => { setQ(value); setPage(1); }} style={{ width: 280 }} />
      <Checkbox checked={includeExcluded} onChange={event => { setIncludeExcluded(event.target.checked); setPage(1); }}>包含已排除记录</Checkbox>
    </Space>
    <LegacyTaskProgress title="暂存拉取进度" task={job} kind="fetch" />
    {(status.error || records.error) && <Alert type="error" title={(status.error || records.error)?.message} />}
    <Table<AnyRecord> rowKey="source_rowid" style={{ marginTop: 12 }} loading={records.isLoading} dataSource={(records.data?.items || []) as AnyRecord[]} scroll={{ x: 950 }} pagination={{ current: page, pageSize: 50, total: Number(records.data?.total || 0), showSizeChanger: false, onChange: setPage }} columns={[
      { title: '旧 ID', dataIndex: 'source_id_raw' }, { title: '日期', render: (_, row) => display((row.raw as AnyRecord)['时间']) },
      { title: '机型 / 客户', render: (_, row) => `${(row.raw as AnyRecord)['机型'] || ''} / ${(row.raw as AnyRecord)['顾客'] || ''}` },
      { title: '工程师', render: (_, row) => display((row.raw as AnyRecord)['工程师']) },
      { title: '管理状态', render: (_, row) => row.missing ? '来源缺失' : row.excluded ? '已排除' : '待本地确认' }, { title: '管理备注', dataIndex: 'management_note' },
      { title: '操作', render: (_, row) => <Space><Button disabled={disabled} onClick={() => { setEditing(row); setNote(String(row.management_note || '')); }}>字段 / 备注</Button><Button disabled={disabled} onClick={() => void action(() => send(`/cache/records/${row.source_rowid}/refresh`), '已刷新此条来源，请重新生成预览')}>刷新此条</Button><Button disabled={disabled} onClick={() => void action(() => send(`/cache/records/${row.source_rowid}`, { excluded: !row.excluded }, 'PATCH'), row.excluded ? '已恢复暂存候选' : '已排除，不参与同步预览')}>{row.excluded ? '恢复' : '排除'}</Button></Space> },
    ]} />
    <Modal open={Boolean(editing)} title="本地暂存原始字段与管理备注" width={850} onCancel={() => setEditing(null)} onOk={() => void action(async () => { await send(`/cache/records/${editing?.source_rowid}`, { management_note: note }, 'PATCH'); setEditing(null); }, '管理备注已保存')}>
      <Input.TextArea aria-label="本地管理备注" value={note} maxLength={2000} onChange={event => setNote(event.target.value)} placeholder="本地管理备注，不改写来源字段" />
      <Descriptions column={1} bordered size="small" items={Object.entries((editing?.raw || {}) as AnyRecord).map(([field, value]) => ({ key: field, label: field, children: display(value) }))} />
    </Modal>
  </Card>;
}

export function LegacyEngineerMappings({ names, mappings, employees, onChange }: {
  names: string[]; mappings: Record<string, string>; employees: AnyRecord[];
  onChange: (name: string, username: string | undefined) => void;
}) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const visibleNames = names.filter(name => name.includes(search.trim()));
  const unmapped = names.filter(name => !mappings[name]).length;
  return <>
    <Space wrap style={{ marginBottom: 12 }}>
      <Input allowClear aria-label="搜索老工程师姓名" placeholder="搜索老工程师姓名，例如李蒙悦" value={search} onChange={event => { setSearch(event.target.value); setPage(1); }} style={{ width: 280 }} />
      <span>共 {names.length} 位工程师，未映射 {unmapped} 位；当前匹配 {visibleNames.length} 位</span>
    </Space>
    <Table<{ name: string }> rowKey="name" size="small" pagination={{ current: page, pageSize, showSizeChanger: true, pageSizeOptions: [10, 50, 100], showTotal: total => `共 ${total} 位工程师`, onChange: (nextPage, nextSize) => { setPage(nextPage); setPageSize(nextSize); } }} dataSource={visibleNames.map(name => ({ name }))} columns={[
      { title: "老工程师姓名", dataIndex: "name" },
      { title: "映射状态", render: (_, row) => <Tag color={mappings[row.name] ? "green" : "orange"}>{mappings[row.name] ? "已映射" : "未映射"}</Tag> },
      { title: "新系统工程师", render: (_, row) => <Select style={{ width: 240 }} allowClear showSearch optionFilterProp="label" placeholder="暂不映射" value={mappings[row.name]} options={employees.filter(employee => employee.username).map(employee => ({ value: String(employee.username), label: String(employee.name || employee.username) }))} onChange={username => onChange(row.name, username)} /> },
    ]} />
  </>;
}

function LegacyRecords({ notify, openOrderDetail }: Props) {
  const [page, setPage] = useState(1);
  const [classification, setClassification] = useState("");
  const records = useQuery({ queryKey: ["legacy", "records", page, classification], queryFn: () => api<AnyRecord>(`/api/legacy-import/records?offset=${(page - 1) * 50}&limit=50&classification=${classification}`), refetchInterval: 4000 });
  const [selected, setSelected] = useState<number>();
  const summary = useQuery({ queryKey: ["legacy", "summary"], queryFn: () => api<AnyRecord>("/api/legacy-import/summary"), refetchInterval: 10000 });
  return <Card title="已导入维修记录">
    {summary.data && <Alert type="info" style={{ marginBottom: 16 }} title="历史金额独立统计" description={<span>{Object.entries((summary.data.historical_amounts || {}) as AnyRecord).map(([field, total]) => `${field}: ${total}（未知 ${((summary.data?.unknown_amount_counts || {}) as AnyRecord)[field] || 0} 条）`).join("；")}。{String(summary.data.note)}</span>} />}
    <Space><Select aria-label="后续处理方式" style={{ width: 190 }} value={classification} onChange={value => { setClassification(value); setPage(1); }} options={[{ value: "", label: "全部处理方式" }, { value: "history", label: labels.history }, { value: "active", label: labels.active }, { value: "unknown", label: labels.unknown }]} /><Button onClick={() => void records.refetch()}>刷新</Button></Space>
    {records.error && <Alert type="error" title={records.error.message} />}
    <Table<AnyRecord> style={{ marginTop: 16 }} rowKey="repair_order_id" loading={records.isLoading} dataSource={(records.data?.items || []) as AnyRecord[]} scroll={{ x: 1000 }} pagination={{ current: page, pageSize: 50, total: Number(records.data?.total || 0), showSizeChanger: false, onChange: setPage }} columns={[
      { title: "旧 ID", dataIndex: "source_id_raw" }, { title: "新工单", dataIndex: "order_no" }, { title: "机型", dataIndex: "model" }, { title: "客户", dataIndex: "customer_name" },
      { title: "后续处理方式", dataIndex: "classification", render: v => labels[String(v)] }, { title: "归属", dataIndex: "ownership", render: v => labels[String(v)] },
      { title: "历史报价", render: (_, r) => (r.amounts as AnyRecord)?.["报价"] == null ? "未知" : display((r.amounts as AnyRecord)["报价"]) }, { title: "来源", render: (_, r) => r.missing ? <Tag color="orange">来源缺失</Tag> : "正常" },
      { title: "操作", render: (_, r) => <Space><Button onClick={() => setSelected(Number(r.repair_order_id))}>字段 / 接管</Button>{openOrderDetail && <Button onClick={() => openOrderDetail(r)}>工单详情</Button>}</Space> },
    ]} />
    <Modal open={Boolean(selected)} title="来源记录与接管" width={920} onCancel={() => setSelected(undefined)} footer={null}>{selected && <LegacyOrderPanel orderId={selected} notify={notify} />}</Modal>
  </Card>;
}

export function LegacyOrderPanel({ orderId, notify }: { orderId: number | string; notify: Props["notify"] }) {
  const qc = useQueryClient();
  const me = useQuery({ queryKey: ["me", "legacy"], queryFn: () => api<AnyRecord>("/api/me") });
  const admin = ["admin", "boss"].includes(String(me.data?.role));
  const detail = useQuery({ queryKey: ["legacy", "order", orderId], queryFn: () => api<AnyRecord | null>(`/api/legacy-import/orders/${orderId}`) });
  const employees = useQuery({ queryKey: ["legacy", "employees"], queryFn: () => api<AnyRecord[]>("/api/dispatch-engineers"), enabled: admin });
  const [customerSearch, setCustomerSearch] = useState("");
  const customers = useQuery({ queryKey: ["legacy", "customers", customerSearch], queryFn: () => api<AnyRecord[]>(`/api/customers?q=${encodeURIComponent(customerSearch)}`), enabled: admin && Boolean(customerSearch) });
  const [form] = Form.useForm();
  const { busy, action } = useLegacyAction(notify);
  const [lockCode, setLockCode] = useState<string | null>(null);
  const value = detail.data;
  if (detail.error) return <Alert type="error" title={detail.error.message} />;
  if (!value) return null;
  return <Card title={`老系统来源 · 旧账单 ${value.source_id_raw}`} style={{ margin: "16px 0" }}>
    <Descriptions items={[
      { key: "ownership", label: "归属", children: labels[String(value.ownership)] }, { key: "classification", label: "后续处理方式", children: labels[String(value.classification)] },
      { key: "synced", label: "同步时间", children: String(value.synced_at) }, { key: "taken", label: "接管人 / 时间", children: `${value.taken_by || "—"} ${value.taken_at || ""}` },
      { key: "balance", label: "历史已收 / 期初待收", children: `${display(value.initial_paid)} / ${display(value.initial_due)}` },
    ]} />
    {value.missing ? <Alert type="warning" title="来源记录缺失，请核对后处理" /> : null}
    <details><summary>全部 23 个原始字段、历史金额与配件</summary><Descriptions bordered column={1} size="small" items={Object.entries(value.raw as AnyRecord).map(([key, val]) => ({ key, label: key, children: display(val) }))} /><p>历史金额：{JSON.stringify(value.amounts)}；历史配件：{JSON.stringify(value.parts)}</p></details>
    <Button size="small" style={{ marginTop: 12 }} disabled={busy} onClick={() => void action(async () => { const data = await send(`/orders/${orderId}/lock-code`); setLockCode(String((data.raw as AnyRecord)["锁屏密码"] || "（空）")); }, "已读取锁屏密码，操作已记录")}>按权限查看锁屏密码</Button>
    {lockCode !== null && <Space style={{ marginLeft: 12 }}><span>{lockCode}</span><Button size="small" onClick={() => setLockCode(null)}>隐藏</Button></Space>}
    <Table<AnyRecord> size="small" style={{ marginTop: 12 }} rowKey="attachment_id" pagination={false} dataSource={(value.attachments || []) as AnyRecord[]} columns={[{ title: "图片引用", dataIndex: "reference" }, { title: "复制状态", dataIndex: "status" }, { title: "说明", dataIndex: "error" }]} />
    {admin && value.ownership === "following" && value.classification !== "history" && <Card title="确认接管至新系统" style={{ marginTop: 16 }}>
      <Alert type="info" title="接管后老系统变化仅提示，后续业务由新系统维护。历史金额保留，收费按确认的期初待收金额继续。" />
      <Form form={form} layout="vertical" onFinish={values => Modal.confirm({ title: "确认接管这张工单？", content: "请确认当前阶段、客户设备及历史收款口径，接管后停止来源业务更新。", onOk: async () => {
        await action(() => send(`/orders/${orderId}/takeover`, { ...values, target_fingerprint: value.target_fingerprint }), "接管完成");
        await qc.invalidateQueries({ queryKey: ["repair-workbench"] }); await qc.invalidateQueries({ queryKey: ["repair-workbench-detail", orderId] });
      } })}>
        <Form.Item name="status" label="当前阶段" rules={[{ required: true }]}><Select options={["已开单", "检测中", "已报价", "处理中", "待交付", "已交付"].map(s => ({ value: s, label: s }))} /></Form.Item>
        <Form.Item name="assigned_to" label="指派工程师"><Select allowClear options={(employees.data || []).filter(e => e.username).map(e => ({ value: String(e.username), label: String(e.name || e.username) }))} /></Form.Item>
        <Form.Item name="customer_id" label="关联客户（可选，保留原客户快照）"><Select showSearch filterOption={false} onSearch={setCustomerSearch} allowClear options={(customers.data || []).map(c => ({ value: Number(c.customer_id), label: `${c.name} · ${c.phone || ""}` }))} /></Form.Item>
        <Form.Item name="initial_paid" label="历史已收金额" rules={[{ required: true }]}><InputNumber min={0} precision={2} stringMode style={{ width: "100%" }} /></Form.Item>
        <Form.Item name="initial_due" label="期初待收金额" rules={[{ required: true }]}><InputNumber min={0} precision={2} stringMode style={{ width: "100%" }} /></Form.Item>
        <Form.Item name="confirmed" valuePropName="checked" rules={[{ validator: (_, checked) => checked ? Promise.resolve() : Promise.reject(new Error("请核对客户、设备和当前阶段")) }]}><Checkbox>已核对客户、设备、当前维修阶段及期初金额</Checkbox></Form.Item>
        <Button type="primary" htmlType="submit" disabled={busy || Boolean(value.missing)}>确认接管</Button>
      </Form>
    </Card>}
  </Card>;
}
