import { $ } from './dom.js';

export const TASK_TYPES = {
  text: {
    id: 'text',
    outField: 'text',
    show: ['textHint', 'backendModelCard'],
    runLabel: '▶ 开始生成文本（文本列为空的行）',
    skipLabel: '已有文案,跳过',
    outputLabel: '输出列（生成的文案写这里，选文本列）',
    inputLabel: '输入列（点选，可多个；📎附件列=发给视觉模型看图写文）',
    needDirectKey: false,
    needBackendModel: true,
  },
  image: {
    id: 'image',
    outField: 'attach',
    show: ['imgHint', 'sizeRow', 'directApiCard'],
    runLabel: '▶ 开始出图（附件列为空的行）',
    skipLabel: '已有图,跳过',
    outputLabel: '输出列（生成的图写这里，选附件列）',
    inputLabel: '输入列（点选，可多个；📎附件列=作产品参考图）',
    needDirectKey: true,
    needBackendModel: false,
  },
  video: {
    id: 'video',
    outField: 'attach',
    show: ['videoCfg', 'resumeBtn'],
    runLabel: '▶ 开始生成视频（附件列为空的行）',
    skipLabel: '已有片,跳过',
    outputLabel: '输出列（生成的视频写这里，选附件列）',
    inputLabel: '输入列（点选，可多个；📎附件列=当首帧或参考图）',
    needDirectKey: false,
    needBackendModel: false,
  },
  crawl: {
    id: 'crawl',
    outField: 'both',
    show: ['crawlHint', 'crawlCfg'],
    runLabel: '▶ 开始爬取（输出为空的行）',
    skipLabel: '已有内容,跳过',
    outputLabel: '输出列（爬取模式请在上方选文本列/附件列）',
    inputLabel: '输入列（可选；用于【列名】拼 URL 或当额外上下文）',
    needDirectKey: false,
    needBackendModel: false,
  },
};

const TOGGLE_IDS = ['textHint', 'imgHint', 'crawlHint', 'sizeRow', 'videoCfg', 'resumeBtn', 'crawlCfg', 'backendModelCard', 'directApiCard'];

export const taskType = () => $('taskType').value;
export const currentTask = () => TASK_TYPES[taskType()] || TASK_TYPES.text;
export const isVideoMode = () => taskType() === 'video';
export const isTextMode = () => taskType() === 'text';
export const isImageMode = () => taskType() === 'image';
export const isCrawlMode = () => taskType() === 'crawl';
export const runBtnLabel = () => currentTask().runLabel;

export function applyTaskUI() {
  const t = currentTask();
  const show = new Set(t.show);
  for (const id of TOGGLE_IDS) {
    const el = $(id);
    if (el) el.style.display = show.has(id) ? '' : 'none';
  }
  $('outputLabel').textContent = t.outputLabel;
  $('inputLabel').textContent = t.inputLabel;
  const outSel = $('outputSel');
  if (outSel) outSel.parentElement && null;
  $('outputSel').style.display = t.outField === 'both' ? 'none' : '';
  $('outputLabel').style.display = t.outField === 'both' ? 'none' : '';
}
