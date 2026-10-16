from pathlib import Path
import json, pandas as pd, numpy as np
from difflib import SequenceMatcher

ROOT=Path(__file__).resolve().parent
RAW=ROOT/'raw'; CLEAN=ROOT/'clean'; OUT=ROOT/'out'
CFG=json.loads((CLEAN/'config.json').read_text(encoding='utf-8'))

def norm(x):
    import re
    return re.sub(r'[^a-z0-9]+',' ',str(x).lower()).strip()

def load_inputs():
    emp=pd.read_csv(RAW/'karnataka_udyam_employment_nov2022.csv')
    mix=pd.read_csv(CLEAN/'occupation_mix_prior.csv')
    cw=pd.read_csv(CLEAN/'crosswalk.csv')
    iti=pd.read_csv(RAW/'iti_division_training_2020_21.csv')
    return emp,mix,cw,iti

def run():
    emp,mix,cw,iti=load_inputs()
    state_seats=float(iti[['one_year_sanctioned','two_year_sanctioned']].sum().sum())
    state_adm=float(iti[['one_year_admitted','two_year_admitted']].sum().sum())
    state_pass=float(iti[['one_year_passed_out','two_year_passed_out']].sum().sum())
    fill_mode=state_adm/state_seats; completion_mode=state_pass/state_adm
    emp['share']=emp.udyam_employment/emp.udyam_employment.sum()
    emp['manufacturing_proxy']=emp.udyam_employment*0.104
    emp['iti_seats_proxy']=emp['share']*state_seats
    # crosswalk weights by NCO group; broad NCO prior for manufacturing demand
    cw_w=cw.groupby('nco_group_2digit').statewide_course_weight.sum().to_dict()
    mix_groups=mix.nco_group_2digit.astype(str).tolist()
    for g,v in {'21':0.05,'31':cw_w.get('31',0.05),'72':cw_w.get('72',0.54),'74':cw_w.get('74',0.29),'81':cw_w.get('81',0.06),'93':0.01}.items(): cw_w[g]=v
    z=sum(cw_w.get(g,0) for g in mix_groups); cw_w={g:cw_w.get(g,0)/z for g in mix_groups}
    rng=np.random.default_rng(CFG['random_seed'])
    out=[]
    for _,r in emp.iterrows():
      for _,o in mix.iterrows():
        base=r.manufacturing_proxy*o.share_within_manufacturing
        seats=r.iti_seats_proxy*cw_w.get(str(o.nco_group_2digit),0)
        dd=base*rng.triangular(CFG['opening_rate']['low'],CFG['opening_rate']['mode'],CFG['opening_rate']['high'],CFG['monte_carlo_draws'])
        ff=rng.triangular(CFG['seat_fill_rate']['low'],CFG['seat_fill_rate']['mode'],CFG['seat_fill_rate']['high'],CFG['monte_carlo_draws'])
        cc=rng.triangular(CFG['completion_rate']['low'],CFG['completion_rate']['mode'],CFG['completion_rate']['high'],CFG['monte_carlo_draws'])
        pp=rng.triangular(CFG['sector_entry_rate']['low'],CFG['sector_entry_rate']['mode'],CFG['sector_entry_rate']['high'],CFG['monte_carlo_draws'])
        ss=seats*ff*cc*pp
        ratio=ss/np.maximum(dd,1e-9)
        p10,p50,p90=np.quantile(ratio,[.10,.50,.90])
        sig='GAP' if p90<1 else 'SURPLUS' if p10>1 else 'NEEDS DATA'
        out.append([r.district,2022,'Manufacturing',o.nco_group_2digit,o.occupation_label,base,seats,p10,p50,p90,p90-p10,sig])
    df=pd.DataFrame(out,columns=['district','year','industry','nco_group_2digit','occupation_label','demand_stock_proxy','seats_proxy','ratio_p10','ratio_median','ratio_p90','interval_width','signal'])
    df.to_csv(OUT/'ratio_intervals_rebuilt.csv',index=False)
    print('Rebuilt',len(df),'district/occupation rows')

if __name__=='__main__': run()
