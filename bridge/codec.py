"""Portable messages preserve text; foreign tools become quoted historical text."""
import json,uuid,re,os
from datetime import datetime,timezone

def project_key(cwd):
 """Claude Code uses non-ASCII-alphanumeric path characters as hyphens."""
 return re.sub(r'[^a-zA-Z0-9]','-',str(cwd))

def rows(path,warnings):
 with open(path,encoding='utf-8') as f:
  for n,line in enumerate(f,1):
   try:
    value=json.loads(line)
    if not isinstance(value,dict):warnings.append(f'Non-object record at line {n} skipped');continue
    yield value
   except (ValueError,UnicodeError):warnings.append(f'Malformed record at line {n} skipped')

def blocks(content,warnings):
 if isinstance(content,str):return content
 out=[]
 for b in content or []:
  if not isinstance(b,dict):continue
  t=b.get('type','')
  if t in ('text','input_text','output_text'):out.append(b.get('text',''))
  elif t=='tool_use':out.append('[Historical tool call: '+b.get('name','unknown')+']\n'+json.dumps(b.get('input',{}),ensure_ascii=False));warnings.append('Tool calls preserved as text, not executable calls')
  elif t=='tool_result':out.append('[Historical tool result]\n'+blocks(b.get('content',''),warnings))
  else:warnings.append(f'Unsupported content block {t} omitted')
 return '\n'.join(out)

def read_claude(path):
 d={'messages':[],'warnings':[],'cwd':'','id':''};seen=set();parents={}
 for o in rows(path,d['warnings']):
  d['cwd']=o.get('cwd') or d['cwd'];d['id']=o.get('sessionId') or d['id']
  if o.get('isSidechain'):
   d['warnings'].append('Sidechain/subagent records omitted from main conversation');continue
  if o.get('type') not in ('user','assistant'):continue
  uid=o.get('uuid')
  if uid and uid in seen:continue
  if uid:seen.add(uid)
  parent=o.get('parentUuid')
  if parent and uid:
   if parent in parents and parents[parent]!=uid:d['warnings'].append('Conversation branches flattened in file order; branch topology is not recreated')
   parents[parent]=uid
  m=o.get('message',{});role=m.get('role',o['type']);text=blocks(m.get('content',''),d['warnings'])
  if text and role in ('user','assistant'):d['messages'].append({'role':role,'text':text})
 d['warnings']=sorted(set(d['warnings']));return d

def read_codex(path):
 d={'messages':[],'warnings':[],'cwd':'','id':''}
 for o in rows(path,d['warnings']):
  p=o.get('payload',{})
  if o.get('type')=='session_meta':d.update(cwd=p.get('cwd',''),id=p.get('id',''))
  elif o.get('type')=='response_item':
   t=p.get('type')
   if t=='message' and p.get('role') in ('user','assistant'):
    text=blocks(p.get('content'),d['warnings'])
    if text:d['messages'].append({'role':p['role'],'text':text})
   elif t in ('function_call','function_call_output','custom_tool_call','custom_tool_call_output'):
    d['messages'].append({'role':'assistant','text':'[Historical '+t+']\n'+json.dumps(p,ensure_ascii=False)});d['warnings'].append('Tool calls preserved as text, not executable calls')
   elif t=='reasoning':d['warnings'].append('Private reasoning omitted')
  elif o.get('type')=='compacted':
   text=p.get('message')
   if text:d['messages'].append({'role':'assistant','text':'[Historical compaction summary]\n'+text})
 d['warnings']=sorted(set(d['warnings']));return d

def write_claude(doc,path,session_id,cwd):
 parent=None;now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
 with open(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='utf-8') as f:
  for m in doc['messages']:
   uid=str(uuid.uuid4());role=m['role'];content=m['text'] if role=='user' else [{'type':'text','text':m['text']}]
   msg={'role':role,'content':content}
   if role=='assistant':msg.update(id='msg_'+uid,model='imported-context',type='message',stop_reason='end_turn',usage={'input_tokens':0,'output_tokens':0})
   row={'type':role,'uuid':uid,'parentUuid':parent,'sessionId':session_id,'cwd':cwd,'timestamp':now,'isSidechain':False,'userType':'external','version':'2.1.0','message':msg}
   f.write(json.dumps(row,ensure_ascii=False)+'\n');parent=uid
