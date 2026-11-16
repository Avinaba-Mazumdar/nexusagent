import json,collections,sys
d=json.load(open('scratch/bp.json',encoding='utf-8'))
c=collections.Counter((x['severity'],x.get('rule','-')) for x in d['generalDiagnostics'])
for k,v in c.most_common(): print(v,k)
