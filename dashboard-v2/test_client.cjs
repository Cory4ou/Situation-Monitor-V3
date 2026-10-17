const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements={};
const context=vm.createContext({console,Date,Math,Map,document:{
 querySelector:()=>({getContext:()=>({})}),
 getElementById:id=>elements[id]??=( {textContent:'',classList:{toggle(){}},hidden:true} )
}});
vm.runInContext(fs.readFileSync(__dirname+'/static/app.js','utf8').replace(/^start\(\);\s*$/m,''),context);
vm.runInContext(`
for(let i=0;i<40;i++)updateTrails([{id:'test',distance:1+i*.03,bearing:30}],i*1000);
`,context);
assert.equal(vm.runInContext("trails.get('test').points.length",context),32);
vm.runInContext('updateTrails([],140000)',context);
assert.equal(vm.runInContext('trails.size',context),0);
vm.runInContext("alertOK=true;alertData={items:[]};showAlerts()",context);
assert.match(elements.alertStatus.textContent,/NO ACTIVE/);
assert.equal(elements.alertBanner.hidden,true);
vm.runInContext("alertOK=false;alertData={items:[{event:'Test warning',headline:'Fixture',severity:'Severe',expires:Date.now()/1000+60}]};showAlerts()",context);
assert.match(elements.alertStatus.textContent,/UNAVAILABLE/);
assert.match(elements.alertBanner.textContent,/STALE/);
assert.equal(elements.alertBanner.className,'severe');
vm.runInContext("alertOK=true;alertData={items:[{event:'Expired',expires:1}]};showAlerts()",context);
assert.equal(elements.alertBanner.hidden,true);
console.log('Client checks passed: trail limits/expiry, alert all-clear, stale warning, expired alert.');
