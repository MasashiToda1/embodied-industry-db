/* 具身产业库 · 静态站
 * 无框架、无构建。每个 HTML 的 <body data-page="..."> 决定渲染哪个视图。
 * 数据来自 docs/data/*.json，由 scripts/build_site.py 在部署时生成。
 * 硬约束：不出现排名、打分、「头部企业」。只有分布、时间线、关系。
 */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => (s ?? '').toString().replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const qs = new URLSearchParams(location.search);

let D = null;                       // all.json
const orgById = {};
const label = (k, fb) => (D && D.labels[k]) || fb || k;

async function load() {
  if (D) return D;
  D = await (await fetch('data/all.json')).json();
  D.orgs.forEach(o => orgById[o.id] = o);
  D.events.sort((a, b) => sortKey(b) .localeCompare(sortKey(a)));
  return D;
}
// 混合精度日期压成可排序串，粗精度排在区间末尾（与 compile.py 一致）
function sortKey(ev) {
  const d = String(ev.date), p = ev.date_precision;
  if (p === 'year') return d + '-12-31';
  if (p === 'quarter') { const [y, q] = d.split('-Q'); return `${y}-${{ 1: '03-31', 2: '06-30', 3: '09-30', 4: '12-31' }[q]}`; }
  if (p === 'month') return d + '-31';
  return d;
}
const orgZh = id => (orgById[id] && orgById[id].names.zh) || id;
const orgLink = id => `<a href="org.html?id=${encodeURIComponent(id)}">${esc(orgZh(id))}</a>`;
const tierZh = { official: '官方', primary: '一手文件', media: '媒体', aggregator: '聚合', 'first-party': '一手来源' };

/* ---------- 导航与搜索 ---------- */
function nav(active) {
  const tabs = [['index', '时间线'], ['orgs', '主体'], ['axes', '轴 / 收敛'], ['graph', '图谱'], ['signals', '商业信号']];
  $('header').innerHTML = `<div class="wrap"><nav>
    <a class="brand" href="index.html">具身产业库</a>
    ${tabs.map(([k, z]) => `<a class="tab ${k === active ? 'on' : ''}" href="${k}.html">${z}</a>`).join('')}
    <span class="spacer"></span>
    <input id="q" placeholder="搜主体 / 别名 / 产品名 / 事件…" autocomplete="off">
  </nav></div><div id="search-pop"></div>`;
  const q = $('#q'), pop = $('#search-pop');
  q.addEventListener('input', () => renderSearch(q.value.trim(), pop));
  q.addEventListener('focus', () => q.value && renderSearch(q.value.trim(), pop));
  document.addEventListener('click', e => { if (!e.target.closest('nav') && !e.target.closest('#search-pop')) pop.style.display = 'none'; });
}
function renderSearch(text, pop) {
  if (!text) { pop.style.display = 'none'; return; }
  const t = text.toLowerCase();
  const orgs = D.orgs.filter(o => [o.names.zh, o.names.en, ...(o.names.aliases || [])].filter(Boolean).some(n => n.toLowerCase().includes(t))).slice(0, 8);
  const evs = D.events.filter(e => (e.title.zh + ' ' + (e.summary?.zh || '')).toLowerCase().includes(t)).slice(0, 8);
  if (!orgs.length && !evs.length) { pop.innerHTML = '<div class="empty" style="padding:16px">没有匹配</div>'; pop.style.display = 'block'; return; }
  pop.innerHTML =
    (orgs.length ? `<h5>主体 ${orgs.length}</h5>` + orgs.map(o => `<a href="org.html?id=${o.id}"><b>${esc(o.names.zh)}</b> <span class="m">${esc(o.names.en || '')} · ${(o.layers || []).map(l => D.layers[l]).join('、')} · ${o.event_count} 事件</span></a>`).join('') : '') +
    (evs.length ? `<h5>事件 ${evs.length}</h5>` + evs.map(e => `<a href="index.html?ev=${e.id}"><span class="m">${e.date}</span> ${esc(e.title.zh)} <span class="m">${(e.orgs || []).map(o => orgZh(o.id)).join('、')}</span></a>`).join('') : '');
  pop.style.display = 'block';
}

/* ---------- 事件行与展开 ---------- */
function evidenceList(ev) {
  return (ev.evidence || []).map(e => e.url
    ? `<a href="${esc(e.url)}" target="_blank" rel="noopener">${tierZh[e.tier] || e.tier}</a>${e.snapshot ? ` <span class="mono">快照</span>` : ''}`
    : `<span>${tierZh[e.tier] || e.tier}${e.method ? ' · ' + e.method : ''}</span>`).join(' · ');
}
function axesChips(ax) {
  return Object.entries(ax || {}).flatMap(([f, v]) => (Array.isArray(v) ? v : [v]).map(x =>
    `<a class="chip a" href="axes.html?axis=${f}">${label(f)}: ${label(f + ':' + x, x)}</a>`)).join('');
}
function amountStr(a) { if (!a) return ''; const v = a.value; const s = v >= 1e8 ? (v / 1e8).toFixed(2).replace(/\.?0+$/, '') + ' 亿' : v >= 1e4 ? (v / 1e4).toFixed(0) + ' 万' : String(v); return `${s} ${a.currency}`; }
function eventRow(ev, showOrg = true) {
  const orgs = (ev.orgs || []).map(o => orgLink(o.id) + (o.role !== 'subject' ? `<span class="muted">（${D.roles[o.role] || o.role}）</span>` : '')).join('、');
  return `<tr class="ev" data-id="${ev.id}">
    <td class="mono">${ev.date}<div class="muted" style="font-size:10px">${ev.date_precision}${ev.date_basis && ev.date_basis !== 'stated' ? ' · ' + ev.date_basis : ''}</div></td>
    ${showOrg ? `<td>${orgs}</td>` : ''}
    <td><span class="chip">${D.event_types[ev.type] || ev.type}</span></td>
    <td>${esc(ev.title.zh)}</td>
    <td class="right muted">${(ev.evidence || []).length}${ev.corroboration === 'multi' ? ' ✓' : ''}</td>
  </tr>
  <tr class="detail" data-for="${ev.id}" style="display:none"><td colspan="${showOrg ? 5 : 4}"><div class="detail">
    <p class="sum">${esc(ev.summary?.zh || '')}</p>
    ${ev.amount ? `<div><b>金额</b> ${amountStr(ev.amount)}</div>` : ''}
    ${(ev.counterparties || []).length ? `<div><b>对手方</b> ${ev.counterparties.map(esc).join('、')} <span class="muted">（文本，不在 registry）</span></div>` : ''}
    ${ev.date_as_stated ? `<div class="muted">原文时间表述：${esc(ev.date_as_stated)}</div>` : ''}
    <div style="margin:6px 0">${axesChips(ev.axes)}</div>
    <div class="ev-list">来源：${evidenceList(ev)} <span class="mono">· ${ev.id}</span></div>
  </div></td></tr>`;
}
function bindExpand(root) {
  root.addEventListener('click', e => {
    const tr = e.target.closest('tr.ev'); if (!tr || e.target.closest('a')) return;
    const d = root.querySelector(`tr.detail[data-for="${tr.dataset.id}"]`); d.style.display = d.style.display === 'none' ? '' : 'none';
  });
}

/* ---------- ① 时间线 ---------- */
// 筛选条：三个下拉多选，选项只在点开时出现；选中的条件变成 chips 挂在下面
function facetMenu(id, title, options, selected, onChange, { search = false } = {}) {
  // options: [{k, zh, n, group?}]，n＝全库里有多少条事件命中
  const el = document.createElement('div'); el.className = 'facet'; el.dataset.facet = id;
  el.innerHTML = `<button class="fbtn"></button><div class="fpop">${search ? `<input class="fsearch" placeholder="搜取值…" autocomplete="off">` : ''}<div class="flist"></div></div>`;
  const btn = $('.fbtn', el), list = $('.flist', el), s = $('.fsearch', el);
  const paintBtn = () => { const n = selected.size; btn.classList.toggle('on', !!n); btn.innerHTML = `${title}${n ? ` <b>${n}</b>` : ''} <span class="caret">▾</span>`; };
  const paintList = (q = '') => {
    const t = q.toLowerCase(); let lastGroup = null;
    list.innerHTML = options.filter(o => !t || (o.zh + ' ' + (o.group || '')).toLowerCase().includes(t)).map(o => {
      const g = o.group && o.group !== lastGroup ? `<div class="fgroup">${esc(o.group)}</div>` : ''; if (o.group) lastGroup = o.group;
      return g + `<label class="fopt ${selected.has(o.k) ? 'on' : ''} ${o.n ? '' : 'zero'}"><input type="checkbox" data-k="${o.k}" ${selected.has(o.k) ? 'checked' : ''}><span>${esc(o.zh)}</span><em>${o.n}</em></label>`;
    }).join('') || '<div class="empty" style="padding:10px">没有匹配</div>';
    $$('input[type=checkbox]', list).forEach(cb => cb.onchange = () => { cb.checked ? selected.add(cb.dataset.k) : selected.delete(cb.dataset.k); cb.closest('.fopt').classList.toggle('on', cb.checked); paintBtn(); onChange(); });
  };
  if (s) s.oninput = () => paintList(s.value.trim());
  btn.onclick = e => { e.stopPropagation(); const open = el.classList.contains('open'); $$('.facet.open').forEach(f => f.classList.remove('open')); if (!open) { el.classList.add('open'); if (s) { s.value = ''; paintList(); s.focus(); } } };
  $('.fpop', el).onclick = e => e.stopPropagation();
  el.redraw = () => { paintBtn(); paintList(s ? s.value.trim() : ''); };
  el.redraw(); return el;
}
document.addEventListener('click', () => $$('.facet.open').forEach(f => f.classList.remove('open')));
document.addEventListener('keydown', e => { if (e.key === 'Escape') $$('.facet.open').forEach(f => f.classList.remove('open')); });

async function pageIndex() {
  await load(); nav('index');
  const F = { type: new Set(), layer: new Set(), axis: new Set(qs.get('axis') ? [qs.get('axis')] : []) };
  const count = fn => { const m = {}; D.events.forEach(e => fn(e).forEach(k => m[k] = (m[k] || 0) + 1)); return m; };
  const nType = count(e => [e.type]);
  const nLayer = count(e => [...new Set((e.orgs || []).flatMap(o => orgById[o.id]?.layers || []))]);
  const nAxis = count(e => Object.entries(e.axes || {}).flatMap(([f, v]) => (Array.isArray(v) ? v : [v]).map(x => f + ':' + x)));
  const typeOpts = Object.entries(D.event_types).map(([k, zh]) => ({ k, zh, n: nType[k] || 0 })).sort((a, b) => b.n - a.n);
  const layerOpts = Object.entries(D.layers).map(([k, zh]) => ({ k, zh, n: nLayer[k] || 0 })).sort((a, b) => b.n - a.n);
  const axisOpts = Object.keys(nAxis).sort().map(k => ({ k, zh: label(k, k.split(':')[1]), group: label(k.split(':')[0]), n: nAxis[k] }));
  const zh = { type: k => D.event_types[k] || k, layer: k => D.layers[k] || k, axis: k => `${label(k.split(':')[0])}: ${label(k, k.split(':')[1])}` };

  $('main').innerHTML = `<div class="wrap">
    <h1>时间线</h1><div class="sub"></div>
    <div class="fbar" id="fbar"></div><div class="fchips" id="fchips"></div>
    <div class="card"><table><thead><tr><th>日期</th><th>主体</th><th>类型</th><th>事件</th><th class="right">来源</th></tr></thead><tbody id="rows"></tbody></table></div>
  </div>`;
  const rows = $('#rows'); bindExpand(rows);
  const menus = [
    facetMenu('type', '类型', typeOpts, F.type, () => render()),
    facetMenu('layer', '产业层', layerOpts, F.layer, () => render()),
    facetMenu('axis', '轴取值', axisOpts, F.axis, () => render(), { search: true }),
  ];
  menus.forEach(m => $('#fbar').appendChild(m));

  const render = () => {
    const list = D.events.filter(e =>
      (!F.type.size || F.type.has(e.type)) &&
      (!F.layer.size || (e.orgs || []).some(o => (orgById[o.id]?.layers || []).some(l => F.layer.has(l)))) &&
      (!F.axis.size || Object.entries(e.axes || {}).some(([f, v]) => (Array.isArray(v) ? v : [v]).some(x => F.axis.has(f + ':' + x)))));
    rows.innerHTML = list.length ? list.map(e => eventRow(e)).join('') : `<tr><td colspan="5" class="empty">没有匹配的事件</td></tr>`;
    $('.sub').textContent = `${list.length} / ${D.events.length} 条事件 · ${D.orgs.length} 家主体 · 每条都能点回原始来源与快照。点行展开。`;
    const chips = ['type', 'layer', 'axis'].flatMap(f => [...F[f]].map(k => `<span class="fchip" data-f="${f}" data-k="${k}">${esc(zh[f](k))}<i>×</i></span>`));
    $('#fchips').innerHTML = chips.length ? chips.join('') + `<span class="fchip clear" id="f-clear">清除全部</span>` : '';
    $$('.fchip:not(.clear)').forEach(c => $('i', c).onclick = () => { F[c.dataset.f].delete(c.dataset.k); menus.forEach(m => m.redraw()); render(); });
    const cl = $('#f-clear'); if (cl) cl.onclick = () => { Object.values(F).forEach(s => s.clear()); menus.forEach(m => m.redraw()); render(); };
    const want = qs.get('ev'); if (want) { const d = rows.querySelector(`tr.detail[data-for="${want}"]`); if (d) { d.style.display = ''; d.previousElementSibling.scrollIntoView({ block: 'center' }); } }
  };
  render();
}

/* ---------- ② 主体列表 & 主体页 ---------- */
async function pageOrgs() {
  await load(); nav('orgs');
  const id = qs.get('id');
  if (id) return pageOrg(id);
  const byLayer = {};
  D.orgs.forEach(o => (o.layers || []).forEach(l => (byLayer[l] = byLayer[l] || []).push(o)));
  $('main').innerHTML = `<div class="wrap"><h1>主体</h1><div class="sub">${D.orgs.length} 家，按产业层分组；一家可占多层。点名字进主体页。灰字＝暂无事件（stub）。</div>
    ${Object.entries(D.layers).map(([l, z]) => { const list = (byLayer[l] || []).sort((a, b) => b.event_count - a.event_count || a.names.zh.localeCompare(b.names.zh, 'zh')); return `<div class="card" style="margin-bottom:12px"><h3 style="margin:0 0 8px;font-size:14px">${z} <span class="muted" style="font-weight:400">${list.length}</span></h3>
      ${list.map(o => `<a class="tag ${o.event_count ? '' : 'soft'}" href="org.html?id=${o.id}">${esc(o.names.zh)}${o.event_count ? ` <span class="muted">${o.event_count}</span>` : ''}</a>`).join('')}</div>`; }).join('')}</div>`;
}
async function pageOrg(id) {
  const o = orgById[id];
  if (!o) { $('main').innerHTML = `<div class="wrap"><div class="empty">没有这个主体：${esc(id)}</div></div>`; return; }
  const evs = D.events.filter(e => (e.orgs || []).some(x => x.id === id));
  // 关联主体：同一事件里的其他产业主体 + 角色
  const rel = {};
  evs.forEach(e => (e.orgs || []).forEach(x => { if (x.id !== id) (rel[x.id] = rel[x.id] || []).push({ role: x.role, ev: e }); }));
  const myRoleIn = (e) => (e.orgs || []).find(x => x.id === id)?.role;
  const stack = o.stack || {};
  document.title = `${o.names.zh} · 具身产业库`;
  $('main').innerHTML = `<div class="wrap">
    <h1>${esc(o.names.zh)} <span class="muted" style="font-size:14px;font-weight:400">${esc(o.names.en || '')}${o.hq ? ' · ' + Object.values(o.hq).join('') : ''}${o.founded ? ' · ' + o.founded : ''}</span></h1>
    <div class="sub">${(o.layers || []).map(l => `<span class="chip">${D.layers[l] || l}</span>`).join('')}${(o.names.aliases || []).length ? `<span class="muted"> 别名：${o.names.aliases.map(esc).join('、')}</span>` : ''}
      ${o.accounts ? `<span class="muted"> · 监控：${Object.entries(o.accounts).map(([k, v]) => `${k}=${esc(v)}`).join(' ')}</span>` : ''}</div>
    <div class="two">
      <div class="card"><h3 style="margin:0 0 8px;font-size:14px">技术与商业栈 <span class="muted" style="font-weight:400;font-size:12px">历史取值不删，首次可见＝本库收录到的最早证据</span></h3>
        ${Object.keys(stack).length ? `<table><thead><tr><th>轴</th><th>取值</th><th>首次可见</th><th>来源事件</th></tr></thead><tbody>
        ${Object.entries(stack).flatMap(([f, items]) => items.map(it => `<tr><td>${label(f)}</td><td><a class="chip a" href="axes.html?axis=${f}">${label(f + ':' + it.value, it.value)}</a></td><td class="mono">${it.as_of}</td><td><a class="mono" href="index.html?ev=${it.evidence}">${it.evidence.slice(0, 40)}…</a></td></tr>`)).join('')}</tbody></table>` : '<div class="empty">暂无轴取值</div>'}</div>
      <div class="card"><h3 style="margin:0 0 8px;font-size:14px">关联主体 <span class="muted" style="font-weight:400;font-size:12px">来自事件里的角色</span></h3>
        ${Object.keys(rel).length ? `<table><thead><tr><th>主体</th><th>它的角色</th><th>事件</th></tr></thead><tbody>
        ${Object.entries(rel).map(([oid, xs]) => `<tr><td>${orgLink(oid)}</td><td>${[...new Set(xs.map(x => D.roles[x.role] || x.role))].join('、')}</td><td>${xs.map(x => `<a class="mono" href="index.html?ev=${x.ev.id}">${x.ev.date}</a>`).join(' ')}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">暂无关联主体</div>'}
        ${o.upstream?.robotics_notebooks_institution ? `<div class="muted" style="margin-top:10px;font-size:12px">上游：Robotics_Notebooks · ${esc(o.upstream.robotics_notebooks_institution)}</div>` : ''}</div>
    </div>
    <div class="card" style="margin-top:18px"><h3 style="margin:0 0 8px;font-size:14px">时间线 <span class="muted" style="font-weight:400;font-size:12px">${evs.length} 条</span></h3>
      ${evs.length ? `<table><thead><tr><th>日期</th><th>类型</th><th>事件</th><th class="right">来源</th></tr></thead><tbody id="rows">${evs.map(e => eventRow(e, false).replace(/<td><span class="chip">/, m => (myRoleIn(e) && myRoleIn(e) !== 'subject') ? `<td><span class="chip">${D.roles[myRoleIn(e)]}</span><span class="chip">` : m)).join('')}</tbody></table>` : '<div class="empty">暂无收录事件</div>'}</div>
  </div>`;
  const rows = $('#rows'); if (rows) bindExpand(rows);
}

/* ---------- ③ 轴 / 收敛 ---------- */
async function pageAxes() {
  await load(); nav('axes');
  const A = await (await fetch('data/axes.json')).json();
  const fields = Object.keys(D.axes_meta);
  let axis = qs.get('axis') && A[qs.get('axis')] ? qs.get('axis') : (Object.keys(A)[0] || fields[0]);
  let tab = 'stream';
  $('main').innerHTML = `<div class="wrap"><h1>轴 / 收敛</h1>
    <div class="sub">选一条轴。流图看各取值的主体数随时间怎么变——分散度下降就是收敛；热力看谁先谁后、谁换过。都是分布，不是排名。</div>
    <div class="card" style="margin-bottom:12px"><div id="axis-tags">${fields.map(f => `<span class="tag ${f === axis ? 'on' : ''} ${A[f] ? '' : 'soft'}" data-f="${f}">${label(f)}${A[f] ? '' : ' <small>0</small>'}</span>`).join('')}</div>
      <div style="margin-top:8px"><span class="tag ${tab === 'stream' ? 'on' : ''}" data-t="stream">流图</span><span class="tag" data-t="heat">热力</span></div></div>
    <div class="card" id="viz"></div><div class="notice" style="margin-top:12px">样本还少：现在只有几家主体、几十条事件，曲线代表的是「本库收录到了什么」，不是行业全貌。</div></div>`;
  const draw = () => {
    $$('#axis-tags .tag').forEach(t => t.classList.toggle('on', t.dataset.f === axis));
    $$('[data-t]').forEach(t => t.classList.toggle('on', t.dataset.t === tab));
    const ax = A[axis]; const viz = $('#viz');
    if (!ax) { viz.innerHTML = '<div class="empty">这条轴还没有任何主体有取值</div>'; return; }
    tab === 'stream' ? drawStream(viz, ax) : drawHeat(viz, ax);
  };
  $$('#axis-tags .tag').forEach(t => t.onclick = () => { axis = t.dataset.f; history.replaceState(null, '', '?axis=' + axis); draw(); });
  $$('[data-t]').forEach(t => t.onclick = () => { tab = t.dataset.t; draw(); });
  draw();
}
function toDate(s) { s = String(s); if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return new Date(s); if (/^\d{4}-\d{2}$/.test(s)) return new Date(s + '-15'); const q = s.match(/^(\d{4})-Q([1-4])$/); if (q) return new Date(+q[1], q[2] * 3 - 2, 15); if (/^\d{4}$/.test(s)) return new Date(+s, 6, 1); return new Date(s); }
function drawStream(el, ax) {
  const values = Object.keys(ax.values);
  const points = values.flatMap(v => ax.values[v].orgs.map(o => ({ v, t: toDate(o.first_seen) }))).sort((a, b) => a.t - b.t);
  if (!points.length) { el.innerHTML = '<div class="empty">无数据</div>'; return; }
  // 每个月末：各取值累计有多少主体首次可见
  let t0 = d3.timeMonth.floor(points[0].t); const t1 = d3.timeMonth.ceil(new Date());
  if (d3.timeMonth.count(t0, t1) < 6) t0 = d3.timeMonth.offset(t1, -6);   // 样本全在一个月内时也拉出时间感
  const months = d3.timeMonths(t0, d3.timeMonth.offset(t1, 1));
  const series = months.map(m => { const row = { t: m }; values.forEach(v => row[v] = ax.values[v].orgs.filter(o => toDate(o.first_seen) <= d3.timeMonth.offset(m, 1)).length); return row; });
  const W = el.clientWidth - 32, H = 320, m = { t: 20, r: 20, b: 30, l: 36 };
  el.innerHTML = `<div class="legend" style="margin-bottom:6px">${values.map((v, i) => `<i style="background:${d3.schemeTableau10[i % 10]}"></i>${label(ax.zh ? Object.keys(D.axes_meta).find(k => D.axes_meta[k].zh === ax.zh) + ':' + v : v, ax.values[v].zh)} <span class="muted">${ax.values[v].orgs.length}</span>`).join('')}</div>`;
  const svg = d3.select(el).append('svg').attr('width', W).attr('height', H);
  const x = d3.scaleTime().domain([t0, t1]).range([m.l, W - m.r]);
  const stack = d3.stack().keys(values)(series);
  const y = d3.scaleLinear().domain([0, d3.max(stack, s => d3.max(s, d => d[1])) || 1]).nice().range([H - m.b, m.t]);
  const area = d3.area().x(d => x(d.data.t)).y0(d => y(d[0])).y1(d => y(d[1])).curve(d3.curveMonotoneX);
  svg.selectAll('path').data(stack).join('path').attr('d', area).attr('fill', (d, i) => d3.schemeTableau10[i % 10]).attr('opacity', .9);
  svg.append('g').attr('transform', `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(6).tickFormat(d3.timeFormat('%Y-%m'))).selectAll('text').style('font-size', '11px');
  svg.append('g').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(4)).selectAll('text').style('font-size', '11px');
  svg.append('text').attr('x', m.l).attr('y', 12).style('font-size', '11px').style('fill', '#6b6b70').text('主体数（累计首次可见）');
}
function drawHeat(el, ax) {
  const values = Object.keys(ax.values);
  const orgs = [...new Set(values.flatMap(v => ax.values[v].orgs.map(o => o.org)))];
  const first = {}; values.forEach(v => ax.values[v].orgs.forEach(o => first[o.org + '|' + v] = o));
  const dates = Object.values(first).map(o => toDate(o.first_seen).getTime()); const lo = Math.min(...dates), hi = Math.max(...dates);
  const shade = t => { const k = hi > lo ? (t - lo) / (hi - lo) : .5; return `rgba(63,127,230,${.18 + .7 * k})`; };
  el.innerHTML = `<div class="legend" style="margin-bottom:8px">颜色越深＝首次可见越晚。空格＝未见到该取值。</div>
    <div class="heat" style="grid-template-columns:140px repeat(${values.length},1fr)">
      <div class="h"></div>${values.map(v => `<div class="h">${esc(ax.values[v].zh)}</div>`).join('')}
      ${orgs.map(o => `<div class="h"><a href="org.html?id=${o}">${esc(orgZh(o))}</a></div>${values.map(v => { const f = first[o + '|' + v]; return f ? `<div class="v" style="background:${shade(toDate(f.first_seen).getTime())};color:${(toDate(f.first_seen).getTime() - lo) / ((hi - lo) || 1) > .5 ? '#fff' : '#1f4fa8'}"><a href="index.html?ev=${f.event}" style="color:inherit">${f.first_seen}</a></div>` : '<div></div>'; }).join('')}`).join('')}
    </div>`;
}

/* ---------- ④ 图谱 ---------- */
async function pageGraph() {
  await load(); nav('graph');
  const G = await (await fetch('data/graph.json')).json();
  let showShared = false, showAll = false;
  $('main').innerHTML = `<div class="wrap"><h1>图谱</h1>
    <div class="sub">节点＝主体，大小＝事件数。<b>实线＝事件里的关系</b>（投资 / 客户 / 供应），每条能点回事件。灰点＝文本对手方，不在 registry。</div>
    <div class="card" style="margin-bottom:12px"><span class="tag on" id="t-event">事件关系（实线）</span><span class="tag" id="t-shared">共享技术栈（虚线）</span><span class="tag soft" id="t-all">显示无事件的主体</span>
      <span class="legend" style="float:right">拖动节点 · 滚轮缩放 · 点节点进主体页</span></div>
    <div id="graph"></div><div class="tip" id="tip"></div>
    <div class="notice" style="margin-top:12px">图很稀是实况：事件里带主体间关系的还不多。它不会用共享技术栈的虚线填满来显得热闹——那种边任何人拿论文库都能画，投资和采购关系只有事件层里有。</div></div>`;
  const draw = () => {
    const nodes = (showAll ? G.all_nodes.concat(G.nodes.filter(n => n.text)) : G.nodes).map(n => ({ ...n }));
    const ids = new Set(nodes.map(n => n.id));
    const edges = G.edges.filter(e => (e.kind === 'event' || showShared) && ids.has(e.source) && ids.has(e.target)).map(e => ({ ...e }));
    const el = $('#graph'); el.innerHTML = ''; const W = el.clientWidth, H = el.clientHeight;
    const svg = d3.select(el).append('svg').attr('width', W).attr('height', H);
    const g = svg.append('g');
    svg.call(d3.zoom().scaleExtent([.3, 4]).on('zoom', e => g.attr('transform', e.transform)));
    const r = n => n.text ? 7 : 8 + Math.sqrt(n.events || 0) * 5;
    const sim = d3.forceSimulation(nodes).force('link', d3.forceLink(edges).id(d => d.id).distance(d => d.kind === 'shared' ? 140 : 90))
      .force('charge', d3.forceManyBody().strength(-260).distanceMax(420)).force('center', d3.forceCenter(W / 2, H / 2))
      .force('x', d3.forceX(W / 2).strength(.02)).force('y', d3.forceY(H / 2).strength(.03))   // 把孤点拉回画布
      .force('collide', d3.forceCollide(d => r(d) + 14));
    const link = g.append('g').selectAll('line').data(edges).join('line')
      .attr('stroke', d => d.kind === 'shared' ? '#bbb' : '#1a1a1c').attr('stroke-width', d => d.kind === 'shared' ? 1 : 2)
      .attr('stroke-dasharray', d => d.kind === 'shared' ? '4 4' : null).style('cursor', 'pointer');
    const node = g.append('g').selectAll('g').data(nodes).join('g').style('cursor', d => d.text ? 'default' : 'pointer')
      .call(d3.drag().on('start', (e, d) => { d.fx = d.x; d.fy = d.y; }).on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; sim.alpha(.3).restart(); }).on('end', (e, d) => { d.fx = d.fy = null; }));
    node.append('circle').attr('r', r).attr('fill', d => d.text ? '#c8c8cc' : (d.events ? '#1a1a1c' : '#9a9a9e'));
    node.append('text').text(d => d.zh).attr('x', d => r(d) + 4).attr('y', 4).style('font-size', '11px').style('fill', '#1a1a1c');
    const tip = $('#tip');
    link.on('mousemove', (e, d) => { tip.style.display = 'block'; tip.style.left = e.clientX + 12 + 'px'; tip.style.top = e.clientY + 12 + 'px';
      tip.innerHTML = d.kind === 'shared' ? `共享：${d.values.map(v => label(v, v)).join('、')}` : `${(d.roles || []).map(x => D.roles[x] || x).join('、')} · ${d.events.length} 条事件<br><span class="mono">${d.events.slice(0, 3).join('<br>')}</span>`; })
      .on('mouseleave', () => tip.style.display = 'none').on('click', (e, d) => { if (d.kind === 'event') location.href = 'index.html?ev=' + d.events[0]; });
    node.on('click', (e, d) => { if (!d.text) location.href = 'org.html?id=' + d.id; })
      .on('mousemove', (e, d) => { tip.style.display = 'block'; tip.style.left = e.clientX + 12 + 'px'; tip.style.top = e.clientY + 12 + 'px'; tip.innerHTML = `<b>${esc(d.zh)}</b>${d.text ? '<br>文本对手方（不在 registry）' : `<br>${(d.layers || []).map(l => D.layers[l]).join('、')}<br>${d.events} 条事件`}`; })
      .on('mouseleave', () => tip.style.display = 'none');
    sim.on('tick', () => { link.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y); node.attr('transform', d => `translate(${d.x},${d.y})`); });
  };
  $('#t-shared').onclick = e => { showShared = !showShared; e.target.classList.toggle('on', showShared); draw(); };
  $('#t-all').onclick = e => { showAll = !showAll; e.target.classList.toggle('on', showAll); e.target.classList.toggle('soft', !showAll); draw(); };
  draw();
}

/* ---------- ⑤ 商业信号 ---------- */
async function pageSignals() {
  await load(); nav('signals');
  const TYPES = ['funding', 'procurement', 'deployment', 'pricing'];
  const on = new Set(TYPES); let sort = 'date';
  $('main').innerHTML = `<div class="wrap"><h1>商业信号</h1>
    <div class="sub">只看带钱和带客户的四类事件。金额留空的如实显示「未披露」，不填估算。</div>
    <div class="card" style="margin-bottom:12px"><span id="ft">${TYPES.map(t => `<span class="tag on" data-t="${t}">${D.event_types[t]}</span>`).join('')}</span>
      <span style="float:right"><span class="tag on" data-s="date">按日期</span><span class="tag" data-s="amount">按金额</span></span></div>
    <div class="card"><table><thead><tr><th>日期</th><th>主体</th><th>类型</th><th>事件</th><th>对手方</th><th class="right">金额</th><th>场景</th><th class="right">来源</th></tr></thead><tbody id="rows"></tbody></table></div></div>`;
  const rows = $('#rows'); bindExpand(rows);
  const render = () => {
    let list = D.events.filter(e => on.has(e.type));
    if (sort === 'amount') list = [...list].sort((a, b) => (b.amount?.value || -1) - (a.amount?.value || -1));
    rows.innerHTML = list.length ? list.map(e => `<tr class="ev" data-id="${e.id}">
      <td class="mono">${e.date}</td><td>${(e.orgs || []).filter(o => o.role === 'subject').map(o => orgLink(o.id)).join('、') || (e.orgs || []).map(o => orgLink(o.id)).join('、')}</td>
      <td><span class="chip">${D.event_types[e.type]}</span></td><td>${esc(e.title.zh)}</td>
      <td class="muted">${[...(e.counterparties || []), ...(e.orgs || []).filter(o => o.role !== 'subject').map(o => orgZh(o.id) + '（' + D.roles[o.role] + '）')].map(esc).join('、') || '—'}</td>
      <td class="right">${e.amount ? `<b>${amountStr(e.amount)}</b>` : '<span class="muted">未披露</span>'}</td>
      <td>${(Array.isArray(e.axes?.target_scene) ? e.axes.target_scene : e.axes?.target_scene ? [e.axes.target_scene] : []).map(s => `<span class="chip">${label('target_scene:' + s, s)}</span>`).join('') || '<span class="muted">—</span>'}</td>
      <td class="right muted">${(e.evidence || []).length}${e.corroboration === 'multi' ? ' ✓' : ''}</td></tr>
      <tr class="detail" data-for="${e.id}" style="display:none"><td colspan="8"><div class="detail"><p class="sum">${esc(e.summary?.zh || '')}</p><div class="ev-list">来源：${evidenceList(e)} <span class="mono">· ${e.id}</span></div></div></td></tr>`).join('')
      : `<tr><td colspan="8" class="empty">没有匹配</td></tr>`;
  };
  $$('#ft .tag').forEach(t => t.onclick = () => { t.classList.toggle('on'); on.has(t.dataset.t) ? on.delete(t.dataset.t) : on.add(t.dataset.t); render(); });
  $$('[data-s]').forEach(t => t.onclick = () => { sort = t.dataset.s; $$('[data-s]').forEach(x => x.classList.toggle('on', x === t)); render(); });
  render();
}

/* ---------- 入口 ---------- */
document.addEventListener('DOMContentLoaded', () => {
  const page = document.body.dataset.page;
  ({ index: pageIndex, orgs: pageOrgs, org: pageOrgs, axes: pageAxes, graph: pageGraph, signals: pageSignals }[page] || pageIndex)()
    .catch(err => { $('main').innerHTML = `<div class="wrap"><div class="notice">加载失败：${esc(err.message)}。本地预览请先跑 <span class="mono">make site</span> 生成 data/。</div></div>`; console.error(err); });
  const f = document.createElement('footer'); f.innerHTML = `<div class="wrap">具身产业库 · 数据 CC BY 4.0 · 代码 MIT · <a href="https://github.com/MasashiToda1/embodied-industry-db">GitHub</a> · 技术维度承接自 <a href="https://github.com/ImChong/Robotics_Notebooks">Robotics_Notebooks</a> · 不排名、不打分，只有分布与时间线</div>`; document.body.appendChild(f);
});
