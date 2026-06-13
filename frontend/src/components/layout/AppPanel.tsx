import { Card } from "antd";
import { ReactNode } from "react";

type AppPanelProps = {
  title: string;
  note?: string;
  action?: ReactNode;
  children: ReactNode;
};

export function AppPanel({ title, note, action, children }: AppPanelProps) {
  return (
    <Card
      className="app-panel"
      title={<div className="app-panel-title"><h2>{title}</h2>{note && <p>{note}</p>}</div>}
      extra={action}
    >
      {children}
    </Card>
  );
}
