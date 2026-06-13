import type { ThemeConfig } from "antd";

export const antdTheme: ThemeConfig = {
  token: {
    colorPrimary: "#003d9b",
    colorSuccess: "#16a34a",
    colorWarning: "#d97706",
    colorError: "#dc2626",
    colorText: "#1e293b",
    colorTextSecondary: "#64748b",
    colorBorder: "#e2e8f0",
    colorBgLayout: "#f8fafc",
    borderRadius: 8,
    fontFamily: 'Inter, "Microsoft YaHei", "Segoe UI", system-ui, sans-serif',
  },
  components: {
    Button: {
      controlHeight: 38,
      borderRadius: 8,
    },
    Input: {
      controlHeight: 38,
      borderRadius: 8,
    },
    Select: {
      controlHeight: 38,
      borderRadius: 8,
    },
    Table: {
      cellPaddingBlock: 10,
      cellPaddingInline: 14,
      headerBg: "#f1f5f9",
      borderColor: "#e2e8f0",
    },
    Card: {
      borderRadiusLG: 8,
    },
    Tag: {
      borderRadiusSM: 6,
    },
  },
};
