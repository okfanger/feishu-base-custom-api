import { $, log, sleep, selectedInputs } from './dom.js';
import { S } from './state.js';
import { saveCfg, loadCfg, restoreCfg, CHANGE_IDS } from './config.js';
import { currentTask, applyTaskUI, runBtnLabel, isVideoMode, isCrawlMode } from './registry.js';
import { fillOutputSel, listRecordIds, cellFilled, hasInput, buildInput, writeText, writeImage, writeVideoCell, writeAttachments } from './bitable.js';
import { callText, callImage, vidCtx, submitVideo, pollVideo, downloadVideo, callCrawl, vidKind } from './tasks.js';
import { REQ_TIMEOUT_MS, VIDEO_TIMEOUT_MS } from './state.js';
import { extractUrl } from './crawl-ui.js';
import { bindModelsUi, refreshProvidersList } from './models-ui.js';

async function loadSDK() {
  if (window.__BITABLE__) { window.__sdkSource = '内联自托管(零外部请求)'; return window.__BITABLE__; }
  for (const u of ['https://cdn.jsdelivr.net/npm/@lark-base-open/js-sdk@1.0.2/+esm', 'https://esm.sh/@lark-base-open/js-sdk@1.0.2']) {
    try { const m = await import(u); if (m && m.bitable) { window.__sdkSource = 'CDN兜底:' + new URL(u).host; return m.bitable; } } catch (e) {}
  }
  return null;
}

function toggleTaskUI() {
  applyTaskUI();
  if (!S.running) $('runBtn').textContent = runBtnLabel();
  if (S.fieldMetas.length) fillOutputSel();
}

async function refreshTable() {
  S.table = await S.bitable.base.getActiveTable();
  S.tableId = S.table.id;
  const name = await S.table.getName();
  document.querySelector('.sub').textContent = '当前表：' + name + (window.__sdkSource ? ' · SDK:' + window.__sdkSource : '');
  S.fieldMetas = await S.table.getFieldMetaList();
  const cfg = loadCfg();
  const chips = $('inputChips'); chips.innerHTML = '';
  for (const f of S.fieldMetas) {
    const c = document.createElement('span');
    const label = (f.type === 17 ? '📎' : '') + f.name;
    c.className = 'chip' + ((cfg.inputs || []).includes(label) ? ' on' : '');
    c.textContent = label; c.dataset.name = f.name;
    c.onclick = () => { c.classList.toggle('on'); saveCfg(); };
    chips.appendChild(c);
  }
  fillOutputSel();
  const tsel = $('taskCol'); tsel.innerHTML = '';
  const none = document.createElement('option'); none.value = ''; none.textContent = '(不落表·中途关面板未完成的任务会断)'; tsel.appendChild(none);
  for (const f of S.fieldMetas.filter(f => f.type === 1)) {
    const o = document.createElement('option'); o.value = f.id; o.textContent = f.name;
    if (cfg.taskCol === f.id) o.selected = true; tsel.appendChild(o);
  }
}

async function resolveCrawlUrl(rid) {
  const col = $('crawlUrlCol').value;
  if (col) {
    const s = (await S.table.getCellString(col, rid).catch(() => '')) || '';
    if (s.trim()) return s.trim();
  }
  const input = await buildInput(rid);
  if (!input) return '';
  return extractUrl(input.text) || input.text.trim();
}

async function runCrawlRow(rid, signal) {
  const url = await resolveCrawlUrl(rid);
  if (!url || !/^https?:\/\//i.test(url)) throw new Error('没有有效 URL（选 URL 列或在提示词里写链接）');
  const res = await callCrawl(url, signal);
  const mode = $('crawlWriteMode').value;
  let n = 0;
  if (mode === 'text' || mode === 'both') {
    const tf = $('crawlTextOut').value;
    if (!tf) throw new Error('请选择文本输出列');
    await writeText(tf, rid, res.text || '');
    n += (res.text || '').length;
  }
  if (mode === 'attach' || mode === 'both') {
    const af = $('crawlAttachOut').value;
    if (!af) throw new Error('请选择附件输出列');
    const files = res.files || [];
    if (files.length) await writeAttachments(af, rid, files);
  }
  return { n, url: res.url, pages: (res.meta && res.meta.pages) || 1 };
}

async function setTaskCell(rid, text) {
  const fid = $('taskCol').value;
  if (!fid) return;
  try { await S.table.setCellValue(fid, rid, text); } catch (e) { log('· 任务ID写入失败(不影响生成): ' + e.message); }
}

async function getPendingTask(rid) {
  const fid = $('taskCol').value;
  if (!fid) return null;
  let s = ''; try { s = (await S.table.getCellString(fid, rid)) || ''; } catch {}
  const m = s.match(/⏳(ark|oai):([A-Za-z0-9._-]+)/);
  return m ? { kind: m[1], id: m[2] } : null;
}

async function processVideoRecords(recordIds) {
  const outFid = $('outputSel').value;
  const conc = Math.max(1, Math.min(10, parseInt($('concurrency').value) || 3));
  const ctx = vidCtx();
  let done = 0, skip = 0, fail = 0, idx = 0;
  const worker = async (wi) => {
    await sleep(wi * 500);
    while (!S.stopFlag) {
      const i = idx++;
      if (i >= recordIds.length) return;
      const rid = recordIds[i];
      let taskId = '';
      try {
        if ($('skipMode').value === 'skip' && await cellFilled(outFid, rid)) { skip++; log('· 行' + rid.slice(-6) + ' 已有片,跳过'); continue; }
        const pend = await getPendingTask(rid);
        if (pend) { skip++; log('· 行' + rid.slice(-6) + ' 已有在途任务(' + String(pend.id).slice(0, 10) + '…),不重复提交——点「⏯ 续查」取片'); continue; }
        const input = await buildInput(rid);
        if (!input) { skip++; log('· 行' + rid.slice(-6) + ' 无参考图/无提示词,跳过'); continue; }
        const ac = new AbortController(); S.aborters.add(ac);
        const deadline = Date.now() + VIDEO_TIMEOUT_MS;
        const timer = setTimeout(() => ac.abort(), VIDEO_TIMEOUT_MS);
        try {
          taskId = await submitVideo(ctx, input, ac.signal);
          await setTaskCell(rid, '⏳' + ctx.kind + ':' + taskId);
          log('⏳ 行' + rid.slice(-6) + ' 已提交(任务 ' + String(taskId).slice(0, 12) + '…),生成通常2-6分钟');
          const result = await pollVideo(ctx, taskId, ac.signal, deadline);
          const bytes = await downloadVideo(ctx, taskId, result, ac.signal);
          const sz = await writeVideoCell(outFid, rid, bytes);
          await setTaskCell(rid, '✅' + ctx.kind + ':' + taskId);
          done++;
          log('✅ 行' + rid.slice(-6) + ' 成片写入附件列(' + (Math.round(sz / 1024 / 102.4) / 10) + 'MB)');
        } finally { clearTimeout(timer); S.aborters.delete(ac); }
      } catch (e) {
        fail++;
        const msg = e.name === 'AbortError' ? '超时/已停止' : e.message;
        if (taskId) await setTaskCell(rid, (e.permanent ? '❌' : '⏳') + ctx.kind + ':' + taskId + ' ✗' + String(msg).slice(0, 60));
        log('行' + rid.slice(-6) + ' ' + msg, 1);
      }
    }
  };
  await Promise.allSettled(Array.from({ length: Math.min(conc, recordIds.length) }, (_, i) => worker(i)));
  log('── 完成: 成功' + done + ' / 跳过' + skip + ' / 失败' + fail + (S.stopFlag ? ' (手动停止,在途任务仍在云端,可「续查」)' : '') + ' ──');
}

async function findPendingVideoRows() {
  const fid = $('taskCol').value;
  if (!fid) { log('请先在任务配置里选「任务ID列」,续查靠它找回任务号', 1); return []; }
  const outFid = $('outputSel').value;
  const all = await listRecordIds();
  const rows = [];
  for (const rid of all) {
    if (S.stopFlag) break;
    let s = ''; try { s = (await S.table.getCellString(fid, rid)) || ''; } catch {}
    const m = s.match(/⏳(ark|oai):([A-Za-z0-9._-]+)/);
    if (!m) continue;
    if (await cellFilled(outFid, rid)) continue;
    if (m[1] !== vidKind()) { log('· 行' + rid.slice(-6) + ' 是「' + m[1] + '」格式提交的,与当前接口格式不符,跳过'); continue; }
    rows.push({ rid, kind: m[1], id: m[2] });
  }
  return rows;
}

async function resumeVideoTasks(rows) {
  const outFid = $('outputSel').value;
  const conc = Math.max(1, Math.min(10, parseInt($('concurrency').value) || 3));
  const ctx = vidCtx();
  let done = 0, fail = 0, idx = 0;
  const worker = async () => {
    while (!S.stopFlag) {
      const i = idx++;
      if (i >= rows.length) return;
      const { rid, id } = rows[i];
      const ac = new AbortController(); S.aborters.add(ac);
      const deadline = Date.now() + VIDEO_TIMEOUT_MS;
      const timer = setTimeout(() => ac.abort(), VIDEO_TIMEOUT_MS);
      try {
        log('⏯ 行' + rid.slice(-6) + ' 续查任务 ' + String(id).slice(0, 12) + '…');
        const result = await pollVideo(ctx, id, ac.signal, deadline);
        const bytes = await downloadVideo(ctx, id, result, ac.signal);
        const sz = await writeVideoCell(outFid, rid, bytes);
        await setTaskCell(rid, '✅' + ctx.kind + ':' + id);
        done++;
        log('✅ 行' + rid.slice(-6) + ' 成片写入附件列(' + (Math.round(sz / 1024 / 102.4) / 10) + 'MB)');
      } catch (e) {
        fail++;
        const msg = e.name === 'AbortError' ? '超时/已停止' : e.message;
        await setTaskCell(rid, (e.permanent ? '❌' : '⏳') + ctx.kind + ':' + id + ' ✗' + String(msg).slice(0, 60));
        log('行' + rid.slice(-6) + ' ' + msg, 1);
      } finally { clearTimeout(timer); S.aborters.delete(ac); }
    }
  };
  await Promise.allSettled(Array.from({ length: Math.min(conc, rows.length) }, () => worker()));
  log('── 续查完成: 成功' + done + ' / 失败' + fail + ' ──');
}

async function processRecords(recordIds) {
  const t = currentTask();
  const outFid = $('outputSel').value;
  const conc = Math.max(1, Math.min(10, parseInt($('concurrency').value) || 3));
  let done = 0, skip = 0, fail = 0, idx = 0;
  const worker = async (wi) => {
    await sleep(wi * 300);
    while (!S.stopFlag) {
      const i = idx++;
      if (i >= recordIds.length) return;
      const rid = recordIds[i];
      try {
        if ($('skipMode').value === 'skip' && await cellFilled(outFid, rid)) {
          skip++; log('· 行' + rid.slice(-6) + ' ' + t.skipLabel); continue;
        }
        const ac = new AbortController(); S.aborters.add(ac);
        const timer = setTimeout(() => ac.abort(), REQ_TIMEOUT_MS);
        try {
          if (t.id === 'text') {
            const input = await buildInput(rid);
            if (!input) { skip++; log('· 行' + rid.slice(-6) + ' 无参考图/无提示词,跳过'); continue; }
            const txt = await callText(input, ac.signal);
            await writeText(outFid, rid, txt);
            done++;
            log('✅ 行' + rid.slice(-6) + ' 文本写入完成(' + txt.length + '字)');
          } else if (t.id === 'image') {
            const input = await buildInput(rid);
            if (!input) { skip++; log('· 行' + rid.slice(-6) + ' 无参考图/无提示词,跳过'); continue; }
            const res = await callImage(input, ac.signal);
            const sz = await writeImage(outFid, rid, res, ac.signal);
            done++;
            log('✅ 行' + rid.slice(-6) + ' 出图完成(' + (res.edit ? '图生图' : '文生图') + '·' + Math.round(sz / 1024) + 'KB)');
          } else if (t.id === 'crawl') {
            const info = await runCrawlRow(rid, ac.signal);
            done++;
            log('✅ 行' + rid.slice(-6) + ' 爬取完成 ' + info.url + ' (' + info.n + '字)');
          }
        } finally { clearTimeout(timer); S.aborters.delete(ac); }
      } catch (e) {
        fail++;
        log('行' + rid.slice(-6) + ' ' + (e.name === 'AbortError' ? '超时/已停止(不重试)' : e.message), 1);
      }
    }
  };
  await Promise.allSettled(Array.from({ length: Math.min(conc, recordIds.length) }, (_, i) => worker(i)));
  log('── 完成: 成功' + done + ' / 跳过' + skip + ' / 失败' + fail + (S.stopFlag ? ' (手动停止)' : '') + ' ──');
}

function validateBeforeRun() {
  const t = currentTask();
  if (t.id === 'video') {
    if (!$('vidApiBase').value.trim() || !$('vidApiKey').value.trim()) {
      log('视频模式:请先在「🎬 视频模式独立配置」里填 API 地址和 Key', 1); return false;
    }
  } else if (t.needDirectKey && !$('apiKey').value) {
    log('请先填 API Key', 1); return false;
  } else if (t.needBackendModel && !$('modelRef').value) {
    log('请先在①里选择一个后端模型（或到模型库添加）', 1); return false;
  }
  if (t.id === 'crawl') {
    const mode = $('crawlWriteMode').value;
    if ((mode === 'text' || mode === 'both') && !$('crawlTextOut').value) { log('请选择爬取文本输出列', 1); return false; }
    if ((mode === 'attach' || mode === 'both') && !$('crawlAttachOut').value) { log('请选择爬取附件输出列', 1); return false; }
  } else if (!$('outputSel').value) {
    log(t.outField === 'text' ? '请先在表里建一个"文本"字段当输出列' : '请先在表里建一个"附件"字段当输出列', 1);
    return false;
  }
  return true;
}

async function guardedRun(getTargets, allowStopToggle, processor, opts) {
  if (S.running) {
    if (allowStopToggle) { S.stopFlag = true; S.aborters.forEach(a => a.abort()); log('⏹ 停止中…在途请求已中断'); }
    else log('正在运行中,先停止再试', 1);
    return;
  }
  if (!validateBeforeRun()) return;
  if (!(opts && opts.noPrompt) && !isCrawlMode() && !$('prompt').value.trim() && !selectedInputs().length) {
    log('请写提示词,或选一个含提示词/产品图的输入列', 1); return;
  }
  saveCfg();
  S.running = true; S.stopFlag = false;
  const btn = $('runBtn'); btn.textContent = '⏹ 点击停止'; btn.classList.add('stop');
  try {
    try {
      const sel = await S.bitable.base.getSelection();
      if (sel && sel.tableId && sel.tableId !== S.tableId) { await refreshTable(); log('检测到切换了数据表,字段已刷新——请重新确认后再点', 1); return; }
    } catch (e) {}
    const targets = await getTargets();
    if (!targets || !targets.length) { if (!S.stopFlag) log('没有待处理的行(输出已填 或 输入为空)'); return; }
    log('待处理 ' + targets.length + ' 行,并发 ' + ($('concurrency').value || 3));
    await (processor || (isVideoMode() ? processVideoRecords : processRecords))(targets);
  } catch (e) { log('运行出错: ' + e.message, 1); }
  finally { S.running = false; S.stopFlag = false; btn.textContent = runBtnLabel(); btn.classList.remove('stop'); }
}

async function init() {
  S.bitable = await loadSDK();
  if (!S.bitable) { document.body.innerHTML = '<p class="err">SDK 加载失败：请刷新重试;反复失败请联系发布者。</p>'; return; }
  const cfg = loadCfg();
  restoreCfg(cfg);
  CHANGE_IDS.forEach(id => { const el = $(id); if (el) el.addEventListener('change', saveCfg); });
  document.querySelectorAll('#crawlFileFormats input').forEach(el => el.addEventListener('change', saveCfg));
  document.querySelectorAll('#crawlCfg input[type=checkbox]').forEach(el => el.addEventListener('change', saveCfg));
  $('taskType').addEventListener('change', () => { toggleTaskUI(); saveCfg(); });
  toggleTaskUI();
  bindModelsUi();
  try { await refreshProvidersList(); } catch (e) { log('模型库加载失败: ' + e.message, 1); }
  if (cfg.modelRef && $('modelRef')) $('modelRef').value = cfg.modelRef;
  try { await refreshTable(); } catch (e) { log('读取表格失败: ' + (e && e.message ? e.message : e), 1); }
  try {
    S.bitable.base.onSelectionChange(async () => {
      if (S.running) return;
      try {
        const s = await S.bitable.base.getSelection();
        if (s && s.tableId && s.tableId !== S.tableId) { await refreshTable(); log('检测到切换数据表,字段已刷新'); }
      } catch (e) {}
    });
  } catch (e) {}
}

$('runBtn').onclick = () => guardedRun(async () => {
  const all = await listRecordIds();
  const max = parseInt($('maxRows').value) || 10;
  const outFid = $('outputSel').value;
  const targets = [];
  let pend = 0;
  for (const rid of all) {
    if (S.stopFlag) break;
    if (targets.length >= max) break;
    if ($('skipMode').value !== 'overwrite' && await cellFilled(outFid, rid)) continue;
    if (isVideoMode() && await getPendingTask(rid)) { pend++; continue; }
    if (!(await hasInput(rid))) continue;
    targets.push(rid);
  }
  if (pend) log('· ' + pend + ' 行有在途任务已跳过——点「⏯ 续查未完成的视频任务」取片,不重复扣费');
  return targets;
}, true);

$('runSelBtn').onclick = () => guardedRun(async () => {
  const sel = await S.bitable.base.getSelection();
  if (!sel || !sel.recordId) { log('请先在表里点选一个单元格定位到某一行', 1); return []; }
  return [sel.recordId];
}, false);

$('resumeBtn').onclick = () => guardedRun(findPendingVideoRows, false, resumeVideoTasks, { noPrompt: true });

init();
