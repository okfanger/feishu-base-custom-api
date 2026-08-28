import { $ } from './dom.js';
import { S, MAX_IMGS_PER_ROW } from './state.js';
import { loadCfg } from './config.js';
import { selectedInputs } from './dom.js';
import { currentTask, isTextMode } from './registry.js';

export function fieldMetaByName(name) {
  return S.fieldMetas.find(f => f.name === name) || {};
}

export function fillSelect(sel, fields, selected, emptyText) {
  sel.innerHTML = '';
  if (!fields.length) {
    const o = document.createElement('option');
    o.value = '';
    o.textContent = emptyText;
    sel.appendChild(o);
    return;
  }
  for (const f of fields) {
    const o = document.createElement('option');
    o.value = f.id;
    o.textContent = f.name;
    if (selected === f.id) o.selected = true;
    sel.appendChild(o);
  }
}

export function fillOutputSel() {
  const cfg = loadCfg();
  const t = currentTask();
  const texts = S.fieldMetas.filter(f => f.type === 1);
  const atts = S.fieldMetas.filter(f => f.type === 17);
  if (t.outField === 'text') {
    fillSelect($('outputSel'), texts, cfg.output, '(本表没有文本列,请先建一个文本字段)');
  } else if (t.outField === 'attach') {
    fillSelect($('outputSel'), atts, cfg.output, '(本表没有附件列,请先建一个附件字段)');
  }
  fillSelect($('crawlTextOut'), texts, cfg.crawlTextOut || cfg.output, '(没有文本列)');
  fillSelect($('crawlAttachOut'), atts, cfg.crawlAttachOut, '(没有附件列)');
  const urlCols = [{ id: '', name: '(不指定·从提示词里取 URL)' }, ...texts];
  fillSelect($('crawlUrlCol'), urlCols, cfg.crawlUrlCol, '(不指定)');
}

export async function listRecordIds() {
  try {
    const view = await S.table.getActiveView();
    if (typeof view.getVisibleRecordIdListByPage === 'function') {
      const ids = []; let pageToken;
      for (let g = 0; g < 100; g++) {
        const r = await view.getVisibleRecordIdListByPage(pageToken ? { pageToken, pageSize: 200 } : { pageSize: 200 });
        (r.recordIds || []).forEach(x => x && ids.push(x));
        if (!r.hasMore || !r.pageToken) break;
        pageToken = r.pageToken;
      }
      if (ids.length) return ids;
    }
    const v = await view.getVisibleRecordIdList();
    if (v && v.filter(Boolean).length) return v.filter(Boolean);
  } catch (e) {}
  return (await S.table.getRecordIdList()).filter(Boolean);
}

export async function cellFilled(fid, rid) {
  const t = currentTask();
  if (t.id === 'crawl') {
    const mode = $('crawlWriteMode').value;
    if (mode === 'text' || mode === 'both') {
      const tf = $('crawlTextOut').value;
      if (!tf) return false;
      const s = await S.table.getCellString(tf, rid).catch(() => '');
      const textFilled = !!(s && String(s).trim());
      if (mode === 'text') return textFilled;
      if (!textFilled) return false;
    }
    if (mode === 'attach' || mode === 'both') {
      const af = $('crawlAttachOut').value;
      if (!af) return mode === 'attach';
      const v = await S.table.getCellValue(af, rid).catch(() => null);
      return Array.isArray(v) && v.length > 0;
    }
    return false;
  }
  if (isTextMode() || t.outField === 'text') {
    const s = await S.table.getCellString(fid, rid).catch(() => '');
    return !!(s && String(s).trim());
  }
  const v = await S.table.getCellValue(fid, rid).catch(() => null);
  return Array.isArray(v) && v.length > 0;
}

export async function hasInput(rid) {
  if (currentTask().id === 'crawl') {
    const col = $('crawlUrlCol').value;
    if (col) {
      const s = await S.table.getCellString(col, rid).catch(() => '');
      if (s && s.trim()) return true;
    }
  }
  const cols = selectedInputs().map(fieldMetaByName);
  if (!cols.length) return !!$('prompt').value.trim();
  for (const meta of cols) {
    if (meta.type === 17) {
      const c = await S.table.getCellValue(meta.id, rid).catch(() => null);
      if (Array.isArray(c) && c.some(a => ((a && a.type) || '').startsWith('image/'))) return true;
    } else {
      const s = await S.table.getCellString(meta.id, rid).catch(() => '');
      if (s && s.trim()) return true;
    }
  }
  return false;
}

export async function buildInput(recordId) {
  const tpl = $('prompt').value;
  let text = tpl;
  const extra = []; const imageUrls = [];
  for (const n of selectedInputs()) {
    const meta = fieldMetaByName(n);
    if (meta.type === 17) {
      try {
        const cell = await S.table.getCellValue(meta.id, recordId);
        const imgs = (cell || []).filter(a => ((a && a.type) || '').startsWith('image/'));
        for (const att of imgs) {
          if (imageUrls.length >= MAX_IMGS_PER_ROW) break;
          try {
            const u = await S.table.getAttachmentUrl(att.token, meta.id, recordId);
            if (u) imageUrls.push(u);
          } catch {
            try { const u = await S.table.getAttachmentUrl(att.token); if (u) imageUrls.push(u); } catch {}
          }
        }
      } catch {}
    } else {
      let v = ''; try { v = (await S.table.getCellString(meta.id, recordId)) || ''; } catch {}
      v = v.trim();
      if (tpl.includes('【' + n + '】')) text = text.split('【' + n + '】').join(v);
      else if (v) extra.push(v);
    }
  }
  let prompt = text.trim();
  if (extra.length) prompt = prompt ? prompt + '\n' + extra.join('\n') : extra.join('\n');
  if (!imageUrls.length && !prompt) return null;
  return { text: prompt, imageUrls };
}

export async function writeText(fid, rid, text) {
  await S.table.setCellValue(fid, rid, text);
}

export function b64ToBytes(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

export async function writeAttachments(fid, rid, files) {
  if (!files.length) return 0;
  const fileObjs = files.map(f => {
    const bytes = f.bytes || b64ToBytes(f.b64);
    return new File([bytes], f.name, { type: f.mime || 'application/octet-stream' });
  });
  const tokens = await S.bitable.base.batchUploadFile(fileObjs);
  const val = fileObjs.map((file, i) => ({
    name: file.name, size: file.size, type: file.type, token: tokens[i], timeStamp: file.lastModified || Date.now(),
  }));
  await S.table.setCellValue(fid, rid, val);
  return fileObjs.reduce((s, f) => s + f.size, 0);
}

export async function writeImage(fid, rid, res, signal) {
  let bytes;
  if (res.b64) bytes = b64ToBytes(res.b64);
  else {
    const r = await fetch(res.url, { signal });
    if (!r.ok) throw new Error('下载生成图失败 ' + r.status);
    bytes = new Uint8Array(await r.arrayBuffer());
  }
  return writeAttachments(fid, rid, [{ bytes, name: 'ai_' + rid.slice(-6) + '_' + Date.now() + '.png', mime: 'image/png' }]);
}

export async function writeVideoCell(fid, rid, bytes) {
  return writeAttachments(fid, rid, [{
    bytes, name: 'ai_video_' + rid.slice(-6) + '_' + Date.now() + '.mp4', mime: 'video/mp4',
  }]);
}
