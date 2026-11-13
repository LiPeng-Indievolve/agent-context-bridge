"""Loopback-only UI, guarded by random bearer token and same-origin checks."""
import json,secrets,hmac
from http.server import HTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from .scan import scan
from . import __version__

def allowed_request(host,origin,token,expected,port):
 return host==f'127.0.0.1:{port}' and (origin is None or origin==f'http://127.0.0.1:{port}') and hmac.compare_digest(token or '',expected)

PAGE='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Agent Context Bridge</title><style>
:root{font:15px system-ui;color:#dfe9e5;background:#101a18}body{max-width:1100px;margin:40px auto;padding:0 24px}h1{font-size:32px;margin-bottom:6px}p{color:#9fb9ae}button,select,input{font:inherit;padding:10px;border-radius:8px;border:1px solid #425a51;background:#1e302a;color:#e6f5ee}button{cursor:pointer}button.primary{background:#b5f3cf;color:#10271b}nav{display:flex;flex-wrap:wrap;gap:10px;margin:24px 0}table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid #2a4037;padding:12px}td small{display:block;color:#9ab1a8;overflow-wrap:anywhere}pre{white-space:pre-wrap;background:#172720;padding:16px;border-radius:10px;max-height:400px;overflow:auto}input[type=checkbox]{accent-color:#b5f3cf}#status{min-height:24px}details{margin-top:16px}</style>
<h1>Agent Context Bridge <small style="font-size:14px">v__VERSION__ alpha</small></h1><p>本地迁移 Claude Code ↔ Codex · 原始记录只读 · 按项目或对话选择</p>
<nav><button id="scan">扫描工作空间</button><input id="query" placeholder="搜索项目 / 对话标题"><select id="source"><option value="">全部来源</option><option>claude</option><option>codex</option><option>workspace</option></select><select id="project"><option value="">全部项目</option></select><select id="target"><option value="codex">迁移到 Codex</option><option value="claude">迁移到 Claude Code</option></select></nav>
<nav><button id="select">全选当前筛选</button><button id="clear">清空选择</button><button id="preview">预览迁移</button><button class="primary" id="apply">迁移已选</button></nav>
<p id="status">扫描默认跳过记忆观察器会话。额外工作空间通过启动参数 --root 指定。</p><table><thead><tr><th>选择</th><th>对话 / 项目</th><th>来源</th><th>大小</th></tr></thead><tbody id="rows"></tbody></table><details open><summary>预览与结果（含迁移 ID、续接命令、损失说明）</summary><pre id="result">尚未执行迁移</pre></details>
<details open><summary>完成切换：先验证，再归档旧入口</summary><p>导入后先在旧终端输入 /exit，再运行结果中的 resume_command。导入成功不代表模型已能续接。实际验收会调用你配置的 Codex 模型、消耗相应额度；旧入口仅在验收通过后才可归档，完整历史保留。</p><input id="switchId" placeholder="已导入结果中的 migration_id"><button id="verify">实际续接验收（调用模型）</button><button id="switchPreview">预览旧入口</button><button id="finishSwitch">归档对应旧入口</button></details>
<details><summary>回滚</summary><p>输入结果中的 migration_id。Codex 回滚为归档；Claude 文件若被续写，将拒绝删除。备份保留。</p><input id="rollbackId" placeholder="migration_id"><button id="rollback">回滚此迁移</button></details>
<script>
const token=location.hash.slice(1);history.replaceState(null,'',location.pathname);let items=[],selected=new Set(),busy=false;
const el=id=>document.getElementById(id);async function api(path,data){let r=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Bridge-Token':token},body:JSON.stringify(data||{})});let v=await r.json();if(!r.ok)throw Error(v.error||r.status);return v;}
function filtered(){let q=el('query').value.toLowerCase();return items.filter(x=>(!el('source').value||x.source===el('source').value)&&(!el('project').value||x.cwd===el('project').value)&&(x.title+' '+x.cwd).toLowerCase().includes(q));}
function render(){el('rows').replaceChildren();for(let x of filtered()){let tr=document.createElement('tr'),td=document.createElement('td'),cb=document.createElement('input');cb.type='checkbox';cb.checked=selected.has(x.key);cb.onchange=()=>{cb.checked?selected.add(x.key):selected.delete(x.key);status();};td.append(cb);tr.append(td);td=document.createElement('td');let name=document.createElement('span');name.textContent=x.title;let path=document.createElement('small');path.textContent=x.cwd;td.append(name,path);tr.append(td);for(let v of [x.source,(x.bytes/1048576).toFixed(1)+' MB']){td=document.createElement('td');td.textContent=v;tr.append(td);}el('rows').append(tr);}status();}
function status(){el('status').textContent=items.length+' 条记录 · 已选 '+selected.size+' 条 · 当前显示 '+filtered().length+' 条';}
async function run(fn){if(busy)return;busy=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);el('result').textContent='处理中，请勿关闭窗口…';try{el('result').textContent=JSON.stringify(await fn(),null,2);}catch(e){el('result').textContent=e.message;}finally{busy=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);}}
el('scan').onclick=()=>run(async()=>{items=await api('scan');selected.clear();el('project').replaceChildren(new Option('全部项目',''));for(let cwd of [...new Set(items.map(x=>x.cwd))].sort())el('project').add(new Option(cwd,cwd));render();return {records:items.length};});
for(let id of ['query','source','project'])el(id).oninput=render;
el('select').onclick=()=>{for(let x of filtered())if(x.source!==el('target').value)selected.add(x.key);render();};el('clear').onclick=()=>{selected.clear();render();};
function transfer(apply){if(!selected.size)return;if(apply&&!confirm('将创建所选会话的新副本并保留本地背景备份。确认迁移？'))return;run(()=>api('migrate',{keys:[...selected],target:el('target').value,apply}));}
el('verify').onclick=()=>{if(el('switchId').value&&confirm('调用已配置的 Codex 模型做只读续接验收，将消耗额度；不会执行历史任务。继续？'))run(()=>api('verify',{id:el('switchId').value}));};
el('switchPreview').onclick=()=>run(()=>api('finish-switch',{id:el('switchId').value,apply:false}));
el('finishSwitch').onclick=()=>{if(confirm('仅归档与此迁移匹配的旧 Codex 入口；需先通过实际验收。请先 /exit 退出旧窗口。继续？'))run(()=>api('finish-switch',{id:el('switchId').value,apply:true}));};
el('preview').onclick=()=>transfer(false);el('apply').onclick=()=>transfer(true);el('rollback').onclick=()=>{if(confirm('回滚该迁移？'))run(()=>api('rollback',{id:el('rollbackId').value}));};
</script></html>'''

PAGE=PAGE.replace('__VERSION__',__version__)

def switch_action(engine,route,data):
 mid=data.get('id')
 if not isinstance(mid,str)or not mid.strip():raise ValueError('Enter a migration_id from the imported result')
 if route=='/api/verify':
  from .switching import verify
  return verify(engine,mid)
 if route=='/api/finish-switch':
  from .switching import finish_switch
  return finish_switch(engine,mid,data.get('apply')is True)
 raise ValueError('Unknown switch action')

def serve(args,engine):
 token=secrets.token_urlsafe(32);catalog={}
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*_):pass
  def respond(self,status,value,html=False):
   data=(value if html else json.dumps(value,ensure_ascii=False)).encode();self.send_response(status);self.send_header('Content-Type','text/html; charset=utf-8' if html else 'application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'; connect-src 'self'");self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  def do_GET(self):
   if self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}' or self.path!='/':self.respond(403,{'error':'Forbidden'});return
   self.respond(200,PAGE,True)
  def do_POST(self):
   if not allowed_request(self.headers.get('Host'),self.headers.get('Origin'),self.headers.get('X-Bridge-Token'),token,self.server.server_port):self.respond(403,{'error':'Forbidden'});return
   try:
    length=int(self.headers.get('Content-Length','0'))
    if not 0<length<=1048576:raise ValueError('Invalid request size')
    data=json.loads(self.rfile.read(length));route=urlparse(self.path).path
    if route=='/api/scan':
     values=scan(args.claude_home,args.codex_home,args.root,args.include_observers);catalog.clear()
     for i,x in enumerate(values):x['key']=str(i);catalog[str(i)]=x
     result=values
    elif route=='/api/migrate':
     target=data['target'];keys=data['keys'];selected=[catalog[k] for k in keys];represented={x['cwd'] for x in selected if x['source']!='workspace'};result=[]
     for x in selected:
      if x['source']==target or (x['source']=='workspace' and x['cwd'] in represented):continue
      try:result.append(engine.migrate(x,target,data.get('apply') is True))
      except Exception as exc:result.append({'id':x['id'],'status':'failed','error':str(exc)})
    elif route in('/api/verify','/api/finish-switch'):result=switch_action(engine,route,data)
    elif route=='/api/rollback':result=engine.rollback(data['id'])
    else:self.respond(404,{'error':'Not found'});return
    self.respond(200,result)
   except (ValueError,KeyError,TypeError,OSError,RuntimeError,TimeoutError) as exc:self.respond(400,{'error':str(exc)})
 server=HTTPServer(('127.0.0.1',0),Handler)
 print(f'Open locally: http://127.0.0.1:{server.server_port}/#{token}',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:server.server_close()
