import { $ } from './dom.js';

export const CFG_KEY = 'ai-filler-cfg';

const EXTRA_IDS = [
  'modelRef', 'crawlUrlCol', 'crawlWriteMode', 'crawlTextOut', 'crawlTextFormat',
  'crawlAttachOut', 'crawlMdVariant', 'crawlFilter', 'crawlCache', 'crawlExtract',
  'crawlCss', 'crawlExcludedTags', 'crawlExcludedSel', 'crawlWaitFor', 'crawlJs',
  'crawlPageTimeout', 'crawlWordCount', 'crawlCssSchema', 'crawlLlmModel',
  'crawlLlmInstruction', 'crawlDeep', 'crawlDeepDepth', 'crawlDeepPages',
];

const CHECK_IDS = [
  'crawlScanFull', 'crawlIframes', 'crawlOverlay', 'crawlConsent',
  'crawlMagic', 'crawlShadow', 'crawlExtLinks', 'crawlRobots',
];

export const saveCfg = () => {
  const files = [...document.querySelectorAll('#crawlFileFormats input:checked')].map(i => i.value);
  localStorage.setItem(CFG_KEY, JSON.stringify({
    apiBase: $('apiBase').value, apiKey: $('apiKey').value, model: $('model').value, prompt: $('prompt').value,
    inputs: [...document.querySelectorAll('.chip.on')].map(c => c.textContent),
    output: $('outputSel').value, concurrency: $('concurrency').value, maxRows: $('maxRows').value, imgSize: $('imgSize').value,
    taskType: $('taskType').value, taskCol: $('taskCol').value,
    vidApiKind: $('vidApiKind').value, vidApiBase: $('vidApiBase').value, vidApiKey: $('vidApiKey').value,
    vidModel: $('vidModel').value, vidDur: $('vidDur').value, vidRes: $('vidRes').value, vidRatio: $('vidRatio').value, vidImgMode: $('vidImgMode').value,
    crawlFiles: files,
    ...Object.fromEntries(EXTRA_IDS.map(id => [id, $(id) ? $(id).value : ''])),
    ...Object.fromEntries(CHECK_IDS.map(id => [id, !!( $(id) && $(id).checked )])),
  }));
};

export const loadCfg = () => {
  try { return JSON.parse(localStorage.getItem(CFG_KEY)) || {}; } catch { return {}; }
};

export function restoreCfg(cfg) {
  $('apiBase').value = cfg.apiBase || '';
  $('apiKey').value = cfg.apiKey || '';
  $('model').value = cfg.model || '';
  $('prompt').value = cfg.prompt || '';
  if (cfg.concurrency) $('concurrency').value = cfg.concurrency;
  if (cfg.maxRows) $('maxRows').value = cfg.maxRows;
  if (cfg.imgSize) $('imgSize').value = cfg.imgSize;
  if (cfg.taskType) $('taskType').value = cfg.taskType;
  ['vidApiKind', 'vidApiBase', 'vidApiKey', 'vidModel', 'vidDur', 'vidRes', 'vidRatio', 'vidImgMode'].forEach(id => {
    if (cfg[id] != null && cfg[id] !== '') $(id).value = cfg[id];
  });
  EXTRA_IDS.forEach(id => { if ($(id) && cfg[id] != null && cfg[id] !== '') $(id).value = cfg[id]; });
  CHECK_IDS.forEach(id => { if ($(id) && cfg[id] != null) $(id).checked = !!cfg[id]; });
  if (Array.isArray(cfg.crawlFiles)) {
    document.querySelectorAll('#crawlFileFormats input').forEach(i => { i.checked = cfg.crawlFiles.includes(i.value); });
  }
}

export const CHANGE_IDS = [
  'apiBase', 'apiKey', 'model', 'prompt', 'outputSel', 'concurrency', 'maxRows', 'imgSize',
  'taskType', 'taskCol', 'vidApiKind', 'vidApiBase', 'vidApiKey', 'vidModel', 'vidDur',
  'vidRes', 'vidRatio', 'vidImgMode', 'modelRef', ...EXTRA_IDS,
];
