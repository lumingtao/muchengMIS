import { Modal, type ModalProps } from "antd";
import { ReactNode } from "react";

type AppModalProps = {
  children: ReactNode;
  open: boolean;
  onClose: () => void;
  width?: ModalProps["width"];
};

export function AppModal({ children, open, onClose, width = 1240 }: AppModalProps) {
  return (
    <Modal
      centered
      className="app-modal"
      footer={null}
      open={open}
      width={width}
      onCancel={onClose}
    >
      {children}
    </Modal>
  );
}
