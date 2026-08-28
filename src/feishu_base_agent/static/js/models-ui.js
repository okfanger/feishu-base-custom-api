import { $ , log } from './dom.js';
import { saveCfg } from './config.js';

export async function loadModelsIntoSelects() {
  const r = await fetch('/api/models');
  if (!r.ok) throw new Error('读取模型列表失败 ' + r.status);
  const models = await r.json();
  const cfgVal = $('modelRef').value;
  fillModelSelect($('modelRef'), models, cfgVal);
  fillModelSelect($('crawlLlmModel'), models, $('crawlLlmModel').value);
  updateKeyHint(models);
  return models;
}

function fillModelSelect(sel, models, selected) {
  if (!sel) return;
  const prev = selected || sel.value;
  sel.innerHTML = '';
  if (!models.length) {
    const o = document.createElement('option');
    o.value = '';
    o.textContent = '(模型库为空)';
    sel.appendChild(o);
    return;
  }
  for (const m of models) {
    const o = document.createElement('option');
    o.value = m.ref;
    o.textContent = (m.has_key ? '' : '⚠ ') + m.provider_name + ' / ' + m.name + ' (' + m.api + ')';
    if (m.ref === prev) o.selected = true;
    sel.appendChild(o);
  }
}

function updateKeyHint(models) {
  const ref = $('modelRef').value;
  const m = models.find(x => x.ref === ref);
  const el = $('modelKeyHint');
  if (!m) { el.textContent = '打开下方「模型库」添加供应商与 API Key。'; return; }
  if (m.has_key) el.textContent = m.key_source === 'env' ? 'Key 来自环境变量。' : '已配置 Key。';
  else el.innerHTML = '<span class="err">未配置 Key：在模型库填写 api_key 或设置对应环境变量。</span>';
}

export async function refreshProvidersList() {
  const r = await fetch('/api/providers');
  if (!r.ok) throw new Error('读取供应商失败');
  const providers = await r.json();
  const box = $('providersList');
  box.innerHTML = '';
  for (const p of providers) {
    const div = document.createElement('div');
    div.className = 'prov';
    const pill = p.has_key
      ? `<span class="pill">${p.key_source}${p.key_hint ? ' ' + p.key_hint : ''}</span>`
      : '<span class="pill bad">无 Key</span>';
    const models = (p.models || []).map(m => {
      const ref = p.id + '/' + m.id;
      return `<div class="model-row"><span>${m.name} <code>${m.id}</code></span>
        <button class="tiny" data-test="${ref}">测试连通</button></div>`;
    }).join('');
    div.innerHTML = `<h3>${p.name} <code>${p.id}</code> ${pill}</h3>
      <div class="meta">${p.api} · ${p.base_url}</div>
      ${models}
      <div class="form-actions" style="margin-top:6px">
        <button class="tiny" data-edit="${p.id}">编辑</button>
        <button class="tiny danger" data-del="${p.id}">删除</button>
      </div>`;
    box.appendChild(div);
  }
  box.querySelectorAll('[data-test]').forEach(btn => {
    btn.onclick = () => testModel(btn.dataset.test, btn);
  });
  box.querySelectorAll('[data-edit]').forEach(btn => {
    btn.onclick = () => fillForm(providers.find(p => p.id === btn.dataset.edit));
  });
  box.querySelectorAll('[data-del]').forEach(btn => {
    btn.onclick = () => deleteProvider(btn.dataset.del);
  });
  await loadModelsIntoSelects();
}

function parseModelsText(raw) {
  return String(raw || '').split('\n').map(line => line.trim()).filter(Boolean).map(line => {
    const parts = line.split('|').map(s => s.trim());
    const id = parts[0];
    if (!id) return null;
    const name = parts[1] || id;
    const input = (parts[2] || 'text').split(',').map(s => s.trim()).filter(Boolean);
    return { id, name, input: input.length ? input : ['text'] };
  }).filter(Boolean);
}

function modelsToText(models) {
  return (models || []).map(m => `${m.id} | ${m.name} | ${(m.input || ['text']).join(',')}`).join('\n');
}

function fillForm(p) {
  $('providerFormWrap').open = true;
  $('pfMode').value = 'edit';
  $('pfId').value = p.id;
  $('pfId').disabled = true;
  $('pfName').value = p.name || '';
  $('pfApi').value = p.api;
  $('pfBase').value = p.base_url || '';
  $('pfKey').value = '';
  $('pfKey').placeholder = p.key_hint || (p.has_key ? '留空则保留原 Key' : '${ENV_VAR} 或明文');
  $('pfModels').value = modelsToText(p.models);
}

function resetForm() {
  $('pfMode').value = 'create';
  $('pfId').disabled = false;
  $('pfId').value = '';
  $('pfName').value = '';
  $('pfApi').value = 'openai-completions';
  $('pfBase').value = '';
  $('pfKey').value = '';
  $('pfKey').placeholder = '${DEEPSEEK_API_KEY}';
  $('pfModels').value = '';
}

async function saveProvider() {
  const payload = {
    id: $('pfId').value.trim(),
    name: $('pfName').value.trim() || undefined,
    api: $('pfApi').value,
    base_url: $('pfBase').value.trim(),
    models: parseModelsText($('pfModels').value),
  };
  const key = $('pfKey').value.trim();
  if (key) payload.api_key = key;
  if (!payload.id || !payload.base_url) { log('供应商 id 和 Base URL 必填', 1); return; }
  const editing = $('pfMode').value === 'edit';
  const url = editing ? '/api/providers/' + encodeURIComponent(payload.id) : '/api/providers';
  const r = await fetch(url, {
    method: editing ? 'PUT' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { log('保存失败: ' + (data.detail || r.status), 1); return; }
  log('已保存供应商 ' + payload.id);
  resetForm();
  await refreshProvidersList();
  saveCfg();
}

async function deleteProvider(id) {
  if (!confirm('删除供应商 ' + id + '？')) return;
  const r = await fetch('/api/providers/' + encodeURIComponent(id), { method: 'DELETE' });
  if (!r.ok) { log('删除失败 ' + r.status, 1); return; }
  log('已删除 ' + id);
  await refreshProvidersList();
}

async function testModel(ref, btn) {
  const [provider, model] = ref.split('/');
  btn.disabled = true;
  btn.textContent = '测试中…';
  try {
    const r = await fetch('/api/models/' + encodeURIComponent(provider) + '/' + encodeURIComponent(model) + '/test', { method: 'POST' });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || r.status);
    log('连通 ' + ref + ' · ' + data.latency_ms + 'ms · ' + String(data.text || '').slice(0, 80));
  } catch (e) {
    log('连通失败 ' + ref + ': ' + e.message, 1);
  } finally {
    btn.disabled = false;
    btn.textContent = '测试连通';
  }
}

export function bindModelsUi() {
  $('pfSave').onclick = () => saveProvider().catch(e => log(e.message, 1));
  $('pfReset').onclick = resetForm;
  $('modelRef').addEventListener('change', async () => {
    try {
      const models = await (await fetch('/api/models')).json();
      updateKeyHint(models);
    } catch {}
    saveCfg();
  });
}
