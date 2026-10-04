// node tests/test_investor_aliases.cjs [compiled all.json]
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const data = JSON.parse(fs.readFileSync(process.argv[2] || path.join(root, 'docs/data/all.json'), 'utf8'));
const context = vm.createContext({ URLSearchParams, location: { search: '' }, document: { addEventListener() {} }, data });
vm.runInContext(fs.readFileSync(path.join(root, 'docs/app.js'), 'utf8'), context);
vm.runInContext(`D = data; D.orgs.forEach(o => orgById[o.id] = o);`, context);
const run = code => JSON.parse(vm.runInContext(`JSON.stringify(${code})`, context));
const original = JSON.stringify(data.events);
const mixed = run(`investorRows([
  { id: 'one', counterparties: ['阿里巴巴', '阿里巴巴集团'], orgs: [{id:'alibaba-robotics',role:'investor'}] },
  { id: 'one', counterparties: ['阿里巴巴'] },
  { id: 'two', counterparties: ['阿里巴巴集团'] }
])`);
assert.equal(mixed.length, 1);
assert.equal(mixed[0].n, 2);
assert.equal(mixed[0].href, 'org.html?id=alibaba-robotics');
const separate = run(`investorRows([{id:'x',counterparties:['百度','百度战投','BV 百度风投','美团战投','美团龙珠','红杉中国','Sequoia Capital','未审核新名字'] }])`);
assert.equal(separate.length, 8, '集团关系不能触发自动合并');
const tencent = run(`fundingInvestors({id:'x',counterparties:['腾讯投资'],orgs:[{id:'tencent-robotics',role:'investor'}]})`);
assert.equal(tencent.length, 1);
assert.equal(tencent[0].zh, '腾讯');
assert.equal(tencent[0].href, undefined, '腾讯投资不可链接为机器人实验室');
const advisors = run(`fundingInvestors({id:'x',counterparties:['光源资本（财务顾问）','浙江证监局']})`);
assert.equal(advisors.length, 2, '未获批的 C 组本次保持不变');
const rows = run(`investorRows(D.events.filter(e => e.type === 'funding'))`);
assert.equal(JSON.stringify(data.events), original, '不得改动事件');
assert.equal(new Set(rows.map(r => r.key)).size, rows.length);
for (const r of rows) assert.equal(new Set(r.evs.map(e => e.id)).size, r.n);
console.log('PASS: 别名、跨字段与事件去重、集团边界、腾讯链接、C组范围、历史事件不变');
console.log('投资方入口:', rows.length);
for (const name of ['阿里巴巴','腾讯','英诺基金','BV 百度风投','红杉中国','国泰海通创新投']) {
  console.log(name, rows.find(r => r.zh === name)?.n);
}
