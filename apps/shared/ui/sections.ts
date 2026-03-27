import type { CoreAppModuleId } from "./modules";

export type OverviewMetricKey =
  | "files"
  | "url_sources"
  | "last_updated"
  | "status"
  | "active_today"
  | "users_total"
  | "access_granted"
  | "index_errors";

export type CoreSectionCopy = {
  chatTitle: string;
  chatSubtitle: string;
  clearAction: string;
  sendAction: string;
  sendingAction: string;
  sourceTitle: string;
  previewDocumentLabel: string;
  previewExternalLabel: string;
  openAction: string;
  closeAction: string;
  overviewKnowledgeTitle: string;
  overviewUsageTitle: string;
  overviewFocusTitle: string;
  sourceListTitle: string;
  sourceInputLabel: string;
  addUrlAction: string;
  countLabel: (count: number) => string;
  overviewMetricLabel: (key: OverviewMetricKey) => string;
};

const OVERVIEW_METRIC_LABELS: Record<OverviewMetricKey, string> = {
  files: "\u0424\u0430\u0439\u043b\u043e\u0432",
  url_sources: "URL-\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u043e\u0432",
  last_updated: "\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u0435\u0435 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435",
  status: "\u0421\u0442\u0430\u0442\u0443\u0441",
  active_today: "\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0435 \u0441\u0435\u0433\u043e\u0434\u043d\u044f",
  users_total: "\u0412\u0441\u0435\u0433\u043e \u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a\u043e\u0432",
  access_granted: "\u0414\u043e\u0441\u0442\u0443\u043f \u0440\u0430\u0437\u0440\u0435\u0448\u0451\u043d",
  index_errors: "\u041e\u0448\u0438\u0431\u043a\u0438 \u0438\u043d\u0434\u0435\u043a\u0441\u0430\u0446\u0438\u0438",
};

export const CORE_SECTION_COPY: Partial<Record<CoreAppModuleId, Partial<CoreSectionCopy>>> = {
  overview: {
    overviewKnowledgeTitle: "\u0411\u0430\u0437\u0430 \u0437\u043d\u0430\u043d\u0438\u0439",
    overviewUsageTitle: "\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u0435",
    overviewFocusTitle: "\u0424\u043e\u043a\u0443\u0441 \u0437\u0430\u043f\u0440\u043e\u0441\u043e\u0432",
    overviewMetricLabel: (key) => OVERVIEW_METRIC_LABELS[key],
  },
  chat: {
    chatTitle: "\u041f\u043e\u043c\u043e\u0449\u043d\u0438\u043a \u043f\u043e \u0431\u0430\u0437\u0435 \u0437\u043d\u0430\u043d\u0438\u0439",
    chatSubtitle:
      "\u041e\u0442\u0432\u0435\u0447\u0430\u0435\u0442 \u043f\u043e \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430\u043c \u0438 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0430\u043c \u0432\u0441\u0435\u0433\u043e \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430.",
    clearAction: "\u041e\u0447\u0438\u0441\u0442\u0438\u0442\u044c",
    sendAction: "\u0421\u043f\u0440\u043e\u0441\u0438\u0442\u044c",
    sendingAction: "\u041e\u0442\u043f\u0440\u0430\u0432\u043a\u0430...",
    sourceTitle: "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438",
    previewDocumentLabel: "\u041f\u0440\u0435\u0434\u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430",
    previewExternalLabel: "\u0412\u043d\u0435\u0448\u043d\u0438\u0439 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a",
    openAction: "\u041e\u0442\u043a\u0440\u044b\u0442\u044c",
    closeAction: "\u0417\u0430\u043a\u0440\u044b\u0442\u044c",
  },
  sources: {
    sourceListTitle: "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438",
    sourceInputLabel: "\u0421\u0441\u044b\u043b\u043a\u0430",
    addUrlAction: "\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c URL",
    countLabel: (count) => `\u0412\u0441\u0435\u0433\u043e: ${count}`,
  },
};

export function coreSectionCopy(moduleId: CoreAppModuleId): CoreSectionCopy {
  const specific = CORE_SECTION_COPY[moduleId] || {};
  return {
    chatTitle: specific.chatTitle || "\u0420\u0430\u0437\u0434\u0435\u043b",
    chatSubtitle: specific.chatSubtitle || "",
    clearAction: specific.clearAction || "\u041e\u0447\u0438\u0441\u0442\u0438\u0442\u044c",
    sendAction: specific.sendAction || "\u041e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c",
    sendingAction: specific.sendingAction || "\u041e\u0442\u043f\u0440\u0430\u0432\u043a\u0430...",
    sourceTitle: specific.sourceTitle || "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438",
    previewDocumentLabel:
      specific.previewDocumentLabel || "\u041f\u0440\u0435\u0434\u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430",
    previewExternalLabel:
      specific.previewExternalLabel || "\u0412\u043d\u0435\u0448\u043d\u0438\u0439 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a",
    openAction: specific.openAction || "\u041e\u0442\u043a\u0440\u044b\u0442\u044c",
    closeAction: specific.closeAction || "\u0417\u0430\u043a\u0440\u044b\u0442\u044c",
    overviewKnowledgeTitle: specific.overviewKnowledgeTitle || "\u0411\u0430\u0437\u0430 \u0437\u043d\u0430\u043d\u0438\u0439",
    overviewUsageTitle: specific.overviewUsageTitle || "\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u0435",
    overviewFocusTitle: specific.overviewFocusTitle || "\u0424\u043e\u043a\u0443\u0441 \u0437\u0430\u043f\u0440\u043e\u0441\u043e\u0432",
    sourceListTitle: specific.sourceListTitle || "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438",
    sourceInputLabel: specific.sourceInputLabel || "\u0421\u0441\u044b\u043b\u043a\u0430",
    addUrlAction: specific.addUrlAction || "\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c",
    countLabel: specific.countLabel || ((count) => `\u0412\u0441\u0435\u0433\u043e: ${count}`),
    overviewMetricLabel: specific.overviewMetricLabel || ((key) => OVERVIEW_METRIC_LABELS[key]),
  };
}
