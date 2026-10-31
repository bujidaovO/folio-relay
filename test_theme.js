const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/dist/theme.js', 'utf8');
const settle = () => new Promise(setImmediate);

function page({cached, url='http://127.0.0.1:4173/#week', bridge, blockedStorage=false}={}) {
  const domEvents = {}, windowEvents = {}, buttonEvents = {}, attributes = {}, label = {}, dataset = {}, toasts = [];
  let mounted = false;
  const storage = new Map(cached ? [['folio-relay-theme', cached]] : []);
  const button = {querySelector:()=>label, setAttribute:(key,value)=>{attributes[key]=value;}, addEventListener:(key,fn)=>{buttonEvents[key]=fn;}};
  const document = {
    documentElement:{dataset}, readyState:'loading',
    querySelector:()=>({setAttribute:()=>{}}), getElementById:()=>mounted ? button : null,
    addEventListener:(key,fn)=>{domEvents[key]=fn;}
  };
  const location = {href:url};
  const window = {addEventListener:(key,fn)=>{windowEvents[key]=fn;}, toast:message=>toasts.push(message)};
  if (bridge) window.pywebview = {api:bridge};
  const localStorage = {
    getItem:key=>{if(blockedStorage)throw Error('unavailable');return storage.get(key);},
    setItem:(key,value)=>{if(blockedStorage)throw Error('unavailable');storage.set(key,value);}
  };
  vm.runInNewContext(source, {document, window, location, localStorage, URL,
    history:{state:null, replaceState:(_state,_title,next)=>{location.href=String(next);}}});
  return {dataset, storage, attributes, label, location, toasts,
    connect:api=>{window.pywebview={api};windowEvents.pywebviewready();},
    mount:()=>{mounted=true;domEvents.DOMContentLoaded();}, click:()=>buttonEvents.click()};
}

test('browser appearance is set before first paint and survives reload', () => {
  const first = page({cached:'light'});
  assert.equal(first.dataset.theme, 'light');
  first.mount(); first.click();
  assert.equal(first.dataset.theme, 'dark');
  assert.equal(first.attributes['aria-pressed'], 'true');
  assert.equal(first.storage.get('folio-relay-theme'), 'dark');
  const reopened = page({cached:first.storage.get('folio-relay-theme'),url:first.location.href});
  assert.equal(reopened.dataset.theme, 'dark');
  assert.equal(page({cached:'invalid'}).dataset.theme, 'dark');
});

test('a slow native restore cannot undo the user’s explicit theme change', async () => {
  let resolve, saved;
  const pending = new Promise(done=>{resolve=done;});
  const view = page({url:'http://127.0.0.1:4173/?theme=dark',cached:'light',
    bridge:{get_theme:()=>pending,set_theme:async theme=>{saved=theme;}}});
  assert.equal(view.dataset.theme,'dark');
  view.mount(); view.click();
  resolve('dark'); await settle();
  assert.equal(view.dataset.theme,'light');
  assert.equal(saved,'light');
});

test('rapid toggles save in order, keeping the final choice', async () => {
  let finish, saved;
  const calls=[];
  const wait = new Promise(done=>{finish=done;});
  const view=page({bridge:{get_theme:async()=>'dark',set_theme:async theme=>{
    calls.push(theme); if(calls.length===1)await wait; saved=theme;
  }}});
  view.mount(); await settle();
  view.click(); view.click(); view.click(); await settle();
  assert.deepEqual(calls,['light']);
  finish(); await settle();
  assert.deepEqual(calls,['light','dark','light']);
  assert.equal(saved,'light');
});

test('a choice made before native bridge readiness is saved when it connects', async () => {
  let saved;
  const view=page();
  view.mount(); view.click();
  view.connect({get_theme:async()=>'dark',set_theme:async theme=>{saved=theme;}});
  await settle();
  assert.equal(view.dataset.theme,'light');
  assert.equal(saved,'light');
});

test('unavailable storage does not block switching and failed native saves are visible', async () => {
  const view=page({blockedStorage:true,bridge:{get_theme:async()=>'dark',set_theme:async()=>{throw Error('disk');}}});
  view.mount(); await settle(); view.click(); await settle();
  assert.equal(view.dataset.theme,'light');
  assert.equal(view.toasts.length,1);
});
