import json,sys,os
d=json.load(open('scratch/bp.json',encoding='utf-8'))
for want in sys.argv[1:]:
    want=os.path.normpath(want)
    rows=[x for x in d['generalDiagnostics'] if os.path.normpath(x['file']).endswith(want)]
    if not rows: continue
    src=open(rows[0]['file'],encoding='utf-8').read().splitlines()
    print('=====',want)
    seen=set()
    for x in rows:
        ln=x['range']['start']['line']; key=(ln,x.get('rule'))
        if key in seen: continue
        seen.add(key)
        print(f"{ln+1}: [{x.get('rule')}] {x['message'].splitlines()[0][:110]}\n      | {src[ln].strip()[:120]}")
