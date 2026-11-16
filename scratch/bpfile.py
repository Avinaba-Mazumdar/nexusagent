import json,sys,collections,os
d=json.load(open('scratch/bp.json',encoding='utf-8'))
want=os.path.normpath(sys.argv[1]); full=len(sys.argv)>2
rows=[x for x in d['generalDiagnostics'] if os.path.normpath(x['file']).endswith(want)]
for x in rows: print(x['range']['start']['line']+1, x.get('rule'), x['message'].split('\n')[0][:140])
