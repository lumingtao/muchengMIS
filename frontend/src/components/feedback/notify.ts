import type { MessageInstance } from "antd/es/message/interface";
import type { NotificationInstance } from "antd/es/notification/interface";
import type { HookAPI as ModalHookApi } from "antd/es/modal/useModal";

let messageApi: MessageInstance | null = null;
let notificationApi: NotificationInstance | null = null;
let modalApi: ModalHookApi | null = null;

export function bindFeedbackApis(apis: {
  message: MessageInstance;
  notification: NotificationInstance;
  modal: ModalHookApi;
}) {
  messageApi = apis.message;
  notificationApi = apis.notification;
  modalApi = apis.modal;
}

export const notify = {
  success(content: string) {
    void messageApi?.success(content);
  },
  error(content: string) {
    void messageApi?.error(content);
  },
  warning(content: string) {
    void messageApi?.warning(content);
  },
  info(content: string) {
    void messageApi?.info(content);
  },
  detail(title: string, description: string) {
    notificationApi?.info({ message: title, description });
  },
  confirm(options: Parameters<ModalHookApi["confirm"]>[0]) {
    return modalApi?.confirm(options);
  },
};
