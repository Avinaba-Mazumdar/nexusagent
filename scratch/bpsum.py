import json,collections,os
d=json.load(open('scratch/bp.json',encoding='utf-8'))
print(d['summary'])
f=collections.Counter(os.path.relpath(x['file']) for x in d['generalDiagnostics'])
for k,v in f.most_common(): print(v,k)
