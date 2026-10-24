"""Ground-station questions for Sentinel-2A: passes to schedule per day, and what one more
station would add. Run from the repo root with the snapshot in data/raw:
    python -m findings.ground_stations
"""
from pathlib import Path
from datetime import datetime
import numpy as np, pandas as pd
from debris.tle_parser import split_tle_text, parse
from debris.config import RAW_DIR
from debris.propagator import propagate_many, time_grid, gmst_rad
df=pd.DataFrame([parse(l1,l2,n) for n,l1,l2 in split_tle_text((RAW_DIR / "active.tle").read_text())])
START=datetime(2026,10,24,14); offs=np.arange(0,86400,10.0); jd,fr=time_grid(START,offs); g=gmst_rad(jd+fr)
def ecef(row):
    r,_,_=propagate_many([row.tle_line1],[row.tle_line2],jd,fr); r=r[0]; c,s=np.cos(g),np.sin(g)
    return np.stack([c*r[:,0]+s*r[:,1],-s*r[:,0]+c*r[:,1],r[:,2]],1)
def vis(sat,lat,lon,mask=5):
    la,lo=np.radians(lat),np.radians(lon); p=6378.137*np.array([np.cos(la)*np.cos(lo),np.cos(la)*np.sin(lo),np.sin(la)]); u=p/np.linalg.norm(p); d=sat-p
    return np.degrees(np.arcsin((d@u)/np.linalg.norm(d,axis=1)))>mask
def passes(v): return int(((~v[:-1])&v[1:]).sum()+v[0])
def gaps(v):
    out=[];run=0
    for x in v:
        if x:
            if run: out.append(run)
            run=0
        else: run+=1
    if run: out.append(run)
    return np.array(out)*10/60
st={"Svalbard":(78.23,15.41),"Troll":(-72.01,2.53),"Fairbanks":(64.86,-147.85),"Kiruna":(67.86,20.96),"Hartebeesthoek":(-25.89,27.68)}
s2=df[df.name.str.strip()=="SENTINEL-2A"].iloc[0]; sat=ecef(s2)
per={k:vis(sat,*v) for k,v in st.items()}
allv=np.any(list(per.values()),0)
print("S2A passes per station",{k:passes(v) for k,v in per.items()},"total station-passes",sum(passes(v) for v in per.values()),"merged windows",passes(allv),"contact%",allv.mean())
print("Svalbard alone contact%",per["Svalbard"].mean(),"passes",passes(per["Svalbard"]),"longest gap",gaps(per["Svalbard"]).max())
for name,(la,lo) in {"Bengaluru":(13.03,77.51),"Singapore":(1.35,103.82),"Punta Arenas":(-53.15,-70.92),"Hawaii":(19.8,-155.5),"Inuvik":(68.36,-133.72)}.items():
    v=allv|vis(sat,la,lo); gp=gaps(v)
    print("add",name,"contact%",round(v.mean()*100,1),"longest gap",round(gp.max(),1),"median gap",round(np.median(gp),1))
print("base longest gap",gaps(allv).max(),"median",np.median(gaps(allv)))
