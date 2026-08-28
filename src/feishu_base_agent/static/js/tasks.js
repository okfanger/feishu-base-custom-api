import { $ } from './dom.js';
import { log } from './dom.js';
import { S, REQ_TIMEOUT_MS, VIDEO_TIMEOUT_MS, POLL_MS } from './state.js';
import { sleep } from './dom.js';
import { collectCrawlPayload } from './crawl-ui.js';

export async function urlToImage(url, signal) {
  const r = await fetch(url, { signal });
  if (!r.ok) throw new Error('下载参考图失败 ' + r.status);
  const mime = (r.headers.get('content-type') || 'image/png').split(';')[0] || 'image/png';
  const buf = new Uint8Array(await r.arrayBuffer());
  let bin = '';
  const chunk = 0x8000;
  for (let i = 0; i < buf.length; i += chunk) {
    bin += String.fromCharCode.apply(null, buf.subarray(i, i + chunk));
  }
  return { b64: btoa(bin), mime };
}

export async function callText(input, signal) {
  const { text, imageUrls } = input;
  const modelRef = $('modelRef').value;
  if (!modelRef) throw new Error('请先在①里选一个后端模型');
  const images = [];
  for (const u of imageUrls || []) {
    try { images.push(await urlToImage(u, signal)); }
    catch (e) { log('· 参考图下载失败: ' + e.message); }
  }
  const resp = await fetch('/api/text', {
    method: 'POST', signal,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_ref: modelRef, prompt: text || '请根据图片生成内容', images }),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error('文本API ' + resp.status + ': ' + String(data.detail || JSON.stringify(data)).slice(0, 200));
  const out = data.text;
  if (!out) throw new Error('文本返回无内容: ' + JSON.stringify(data).slice(0, 180));
  return String(out).trim();
}

function imagesEndpoint(kind) {
  const b = $('apiBase').value.replace(/\/chat\/completions.*$/, '').replace(/\/+$/, '');
  return b + '/images/' + kind;
}

export async function callImage(input, signal) {
  const { text, imageUrls } = input;
  const size = $('imgSize').value || '1024x1536';
  const model = $('model').value.trim() || 'gpt-image-2';
  const edit = imageUrls.length > 0;
  const url = imagesEndpoint('generations');
  const auth = 'Bearer ' + $('apiKey').value;
  const body = edit ? { model, images: imageUrls, prompt: text, size, response_format: 'url' }
                    : { model, prompt: text, size };
  let resp = await fetch(url, { method: 'POST', signal, headers: { 'Content-Type': 'application/json', 'Authorization': auth }, body: JSON.stringify(body) });
  if (edit && [400, 404, 415, 422].includes(resp.status)) {
    const jsonErr = (await resp.text()).slice(0, 200);
    resp = await fetch(url, {
      method: 'POST', signal,
      headers: { 'Content-Type': 'application/json', 'Authorization': auth },
      body: JSON.stringify({ model, image: imageUrls[0], prompt: text, size, response_format: 'url' }),
    });
    if (!resp.ok) {
      const fallbackErr = (await resp.text()).slice(0, 200);
      throw new Error('生图API ' + resp.status + ': ' + fallbackErr + '；首次错误: ' + jsonErr);
    }
  }
  if (!resp.ok) throw new Error('生图API ' + resp.status + ': ' + (await resp.text()).slice(0, 200));
  const data = await resp.json();
  const first = data.data && data.data[0];
  if (first && first.b64_json) return { b64: first.b64_json, edit };
  if (first && first.url) return { url: first.url, edit };
  throw new Error('生图返回无 b64/url: ' + JSON.stringify(data).slice(0, 180));
}

export const vidKind = () => $('vidApiKind').value;
export const vidModelName = () => $('vidModel').value.trim() || 'doubao-seedance-2-0-260128';
export const vidDurVal = () => Math.max(4, Math.min(15, parseInt($('vidDur').value) || 15));

export function vidBase() {
  let b = $('vidApiBase').value.trim().replace(/\/+$/, '');
  if (vidKind() === 'ark') {
    b = b.replace(/\/chat\/completions.*$/, '').replace(/\/contents\/generations\/tasks.*$/, '').replace(/\/+$/, '');
    const host = b.replace(/^https?:\/\//, '').split('/')[0].replace(/:\d+$/, '');
    if (/\/api\/ark$/.test(b)) b += '/v3';
    else if (/(^|\.)volces\.com$/.test(host) && !/\/api\/v3$/.test(b)) b += '/api/v3';
  } else {
    b = b.replace(/\/chat\/completions.*$/, '').replace(/\/videos.*$/, '').replace(/\/+$/, '');
    if (!/\/v1$/.test(b)) b += '/v1';
  }
  return b;
}

export function vidCtx() {
  return {
    kind: vidKind(), base: vidBase(), key: $('vidApiKey').value.trim(), model: vidModelName(),
    dur: vidDurVal(), res: $('vidRes').value, ratio: $('vidRatio').value, imgMode: $('vidImgMode').value,
  };
}

async function vidFetch(ctx, url, opts, signal) {
  const r = await fetch(url, { ...opts, signal, headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + ctx.key, ...(opts.headers || {}) } });
  const text = await r.text();
  let j = null; try { j = JSON.parse(text); } catch {}
  if (!r.ok) {
    const err = new Error('视频API ' + r.status + ': ' + String((j && j.error && j.error.message) || (j && j.detail) || text).slice(0, 200));
    err.status = r.status;
    throw err;
  }
  return j || {};
}

export async function submitVideo(ctx, input, signal) {
  const { text, imageUrls } = input;
  if (ctx.kind === 'ark') {
    const content = [{ type: 'text', text: (text || '') + ' --resolution ' + ctx.res + ' --ratio ' + ctx.ratio + ' --duration ' + ctx.dur + ' --watermark false' }];
    if (imageUrls.length) {
      if (ctx.imgMode === 'ref') { for (const u of imageUrls) content.push({ type: 'image_url', image_url: { url: u }, role: 'reference_image' }); }
      else { content.push({ type: 'image_url', image_url: { url: imageUrls[0] } }); if (imageUrls.length > 1) log('· 首帧模式只用第1张图,多图请切「参考图」用法'); }
    }
    const j = await vidFetch(ctx, ctx.base + '/contents/generations/tasks', { method: 'POST', body: JSON.stringify({ model: ctx.model, content }) }, signal);
    if (!j.id) throw new Error('提交任务未返回id: ' + JSON.stringify(j).slice(0, 160));
    return j.id;
  }
  let dur = ctx.dur, size;
  if (/sora/i.test(ctx.model)) {
    dur = [4, 8, 12].reduce((a, b) => (Math.abs(b - ctx.dur) < Math.abs(a - ctx.dur) ? b : a));
    if (dur !== ctx.dur) log('· Sora 只支持 4/8/12 秒,本行按 ' + dur + ' 秒提交');
    size = ctx.ratio === '16:9' ? '1280x720' : (ctx.ratio === '9:16' ? '720x1280' : undefined);
  } else {
    const sz = ({ '480p': { '9:16': '480x854', '16:9': '854x480', '1:1': '480x480' }, '720p': { '9:16': '720x1280', '16:9': '1280x720', '1:1': '720x720' }, '1080p': { '9:16': '1080x1920', '16:9': '1920x1080', '1:1': '1080x1080' } })[ctx.res];
    size = sz && sz[ctx.ratio];
  }
  const body = { model: ctx.model, prompt: text, seconds: String(dur) };
  if (size) body.size = size;
  if (imageUrls.length) log('· 中转站格式暂不支持带参考图,本行按纯文生视频提交');
  const j = await vidFetch(ctx, ctx.base + '/videos', { method: 'POST', body: JSON.stringify(body) }, signal);
  const id = j.id || j.task_id;
  if (!id) throw new Error('提交任务未返回id: ' + JSON.stringify(j).slice(0, 160));
  return id;
}

export async function pollVideo(ctx, id, signal, deadline) {
  let bad4xx = 0;
  while (true) {
    if (S.stopFlag) throw new Error('已手动停止(任务仍在云端跑,稍后可「续查」)');
    if (Date.now() > deadline) throw new Error('超' + Math.round(VIDEO_TIMEOUT_MS / 60000) + '分钟未完成,稍后点「续查」再取');
    let j = null;
    try {
      j = await vidFetch(ctx, ctx.kind === 'ark' ? ctx.base + '/contents/generations/tasks/' + id : ctx.base + '/videos/' + id, { method: 'GET' }, signal);
      bad4xx = 0;
    } catch (e) {
      if (e.name === 'AbortError') throw e;
      if (e.status >= 400 && e.status < 500 && e.status !== 429) {
        bad4xx++;
        if (bad4xx >= 3) { e.permanent = true; e.message = '任务查询连续失败(' + e.message + ')——多半是Key错或任务已过保留期,不再重试'; throw e; }
      }
      log('· 查任务 ' + String(id).slice(0, 10) + '… 出错,稍后重试: ' + e.message);
    }
    if (j) {
      const st = j.status;
      if (st === 'succeeded' || st === 'completed') return j;
      if (st === 'failed' || st === 'cancelled' || st === 'expired') {
        const err = new Error('任务' + st + ': ' + String((j.error && j.error.message) || j.failure_reason || '').slice(0, 160));
        err.permanent = true;
        throw err;
      }
    }
    await sleep(POLL_MS);
  }
}

export async function downloadVideo(ctx, id, taskResult, signal) {
  if (ctx.kind === 'oai') {
    const r = await fetch(ctx.base + '/videos/' + id + '/content', { signal, headers: { 'Authorization': 'Bearer ' + ctx.key } });
    if (!r.ok) throw new Error('下载成片失败 ' + r.status);
    return new Uint8Array(await r.arrayBuffer());
  }
  const vurl = taskResult && taskResult.content && (taskResult.content.video_url || taskResult.content.url);
  if (!vurl) throw new Error('任务完成但没拿到视频URL: ' + JSON.stringify(taskResult).slice(0, 160));
  try { const r = await fetch(vurl, { signal }); if (r.ok) return new Uint8Array(await r.arrayBuffer()); } catch {}
  const m = ctx.base.match(/^(.*\/api\/ark)(?:\/|$)/);
  if (!m) throw new Error('浏览器直连下载被拦,且API地址不是本机代理(形如 http://127.0.0.1:8000/api/ark/v3),无法中转下载');
  const r2 = await fetch(m[1] + '/fetch?url=' + encodeURIComponent(vurl), { signal });
  if (!r2.ok) throw new Error('代理下载成片失败 ' + r2.status);
  return new Uint8Array(await r2.arrayBuffer());
}

export async function callCrawl(url, signal) {
  const body = collectCrawlPayload(url);
  const resp = await fetch('/api/crawl', {
    method: 'POST', signal,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error('爬取API ' + resp.status + ': ' + String(data.detail || JSON.stringify(data)).slice(0, 220));
  if (!data.ok) throw new Error(data.error || '爬取失败');
  return data;
}

export { REQ_TIMEOUT_MS, VIDEO_TIMEOUT_MS };
