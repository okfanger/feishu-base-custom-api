export const S = {
  bitable: null,
  table: null,
  tableId: null,
  fieldMetas: [],
  running: false,
  stopFlag: false,
  aborters: new Set(),
};

export const MAX_IMGS_PER_ROW = 3;
export const REQ_TIMEOUT_MS = 200000;
export const VIDEO_TIMEOUT_MS = 25 * 60000;
export const POLL_MS = 10000;
