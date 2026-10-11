export const legacyViews = {
  legacyImport: { label: "导入概览", subtitle: "查看导入准备情况、后台任务与需要继续处理的批次。" },
  legacyCache: { label: "数据暂存", subtitle: "拉取来源账单，在本地搜索、核对、备注和排除记录。" },
  legacyMappings: { label: "映射规则", subtitle: "配置工程师与维修状态对应关系，保存后重新生成预览。" },
  legacySync: { label: "同步审核", subtitle: "从暂存数据生成预览，核对差异并勾选确认同步。" },
  legacyRecords: { label: "导入记录", subtitle: "查询历史数据，核对在修记录并接管至新系统。" },
  legacySource: { label: "连接设置", subtitle: "维护无锡老系统的连接信息并测试连接。" },
};

export type LegacyView = keyof typeof legacyViews;
export const isLegacyView = (view: string): view is LegacyView => Object.prototype.hasOwnProperty.call(legacyViews, view);
export const legacyNavItems = (admin: boolean) => (Object.keys(legacyViews) as LegacyView[])
  .filter(key => admin || key === "legacyRecords")
  .map(key => ({ key, label: legacyViews[key].label }));
