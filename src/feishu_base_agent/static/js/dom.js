export const $ = id => document.getElementById(id);

export const log = (msg, isErr) => {
  const el = $('log');
  el.style.display = 'block';
  el.textContent += (isErr ? '✗ ' : '') + msg + '\n';
  el.scrollTop = el.scrollHeight;
};

export const sleep = ms => new Promise(r => setTimeout(r, ms));

export const selectedInputs = () =>
  [...document.querySelectorAll('.chip.on')].map(c => c.dataset.name || c.textContent.replace(/^📎/, ''));
