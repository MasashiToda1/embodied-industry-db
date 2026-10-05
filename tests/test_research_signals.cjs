const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const data = { events: [
  {id:'recent',type:'hiring_signal',orgs:[{id:'org',role:'subject'}],title:{zh:'<招聘>'},summary:{zh:'事实'},evidence:[{retrieved:'2025-04-01'}]},
  {id:'old',type:'hiring_signal',orgs:[{id:'org',role:'subject'}],title:{zh:'历史'},evidence:[{retrieved:'2024-01-01'}]},
  {id:'other',type:'hiring_signal',orgs:[{id:'org',role:'investor'}],evidence:[{retrieved:'2025-04-01'}]}
], research_signals: [] };
const c = vm.createContext({URLSearchParams, location:{search:''}, document:{addEventListener(){}}, data});
vm.runInContext(fs.readFileSync(path.join(root,'docs/app.js'),'utf8'),c);
vm.runInContext('D = data',c);
const run = code => vm.runInContext(code,c);
assert.equal(run("recentResearch('2025-01-01','2025-04-01')"),true);
assert.equal(run("recentResearch('2024-12-31','2025-04-01')"),false);
assert.equal(run("recentResearch('2025-04-02','2025-04-01')"),false);
assert.equal(run("recentResearch('','2025-04-01')"),false);
assert.equal(run("researchView('org','2025-04-01').recent.length"),1);
assert.equal(run("researchView('org','2025-04-01').older.length"),1);
const before = JSON.stringify(data.events);
let html = run("researchSection('org','2025-04-01')");
assert.ok(html.includes('尚未形成经审核'));
assert.ok(html.includes('&lt;招聘&gt;'));
assert.ok(html.includes('历史研判与证据'));
assert.ok(!html.includes('<招聘>'));
assert.ok(run("researchSection('unknown','2025-04-01')").includes('暂无近 90 天'));
data.research_signals = [
  {id:'old-reading',org:'org',topic:'control',reviewed_on:'2025-04-01',last_observed:'2025-04-01'},
  {id:'latest-reading',org:'org',topic:'control',reviewed_on:'2025-04-02',last_observed:'2024-01-01'}
];
assert.equal(run("researchView('org','2025-04-02').current.length"),0,'不能回退旧判断为当前');
assert.equal(run("researchView('org','2025-04-02').history.length"),2);
data.research_signals = [{id:'approved',org:'org',topic:'control',reviewed_on:'2025-04-02',
  last_observed:'2025-04-01',title:'<方向>',judgment:'<判断>',limitations:'未确认新项目',
  strength:'supported',evidence_events:['recent']}];
html = run("researchSection('org','2025-04-02')");
assert.ok(html.includes('研判 · 证据支持：有支持'));
assert.ok(html.includes('&lt;判断&gt;'));
assert.ok(html.includes('尚不能确认：未确认新项目'));
assert.ok(html.includes('index.html?ev=recent'));
assert.ok(!html.includes('尚未形成经审核'));
assert.equal(JSON.stringify(data.events),before,'不改写历史事实');
console.log('PASS: 90天边界、未知与未来时间、主体角色、审核与核验时间分离、历史版本、空态、转义、事实不变');
