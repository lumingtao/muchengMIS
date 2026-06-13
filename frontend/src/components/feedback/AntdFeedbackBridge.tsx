import { App as AntdApp } from "antd";
import { useEffect } from "react";
import { bindFeedbackApis } from "./notify";

export function AntdFeedbackBridge() {
  const { message, notification, modal } = AntdApp.useApp();

  useEffect(() => {
    bindFeedbackApis({ message, notification, modal });
  }, [message, notification, modal]);

  return null;
}
