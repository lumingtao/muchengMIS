import { Empty, Result, Spin } from "antd";

export function QueryState({ loading, error }: { loading: boolean; error: unknown }) {
  if (loading) {
    return (
      <div className="query-state">
        <Spin />
        <span>正在读取业务数据。</span>
      </div>
    );
  }
  if (error) {
    return (
      <Result
        className="query-state-result"
        status="error"
        title="加载失败"
        subTitle={error instanceof Error ? error.message : "未知错误"}
      />
    );
  }
  return <Empty className="query-state-result" description="暂无数据" />;
}
