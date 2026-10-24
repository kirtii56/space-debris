"""Two more questions from the same snapshot.

A. Space weather: how many active satellites sit in each altitude band (lower = more drag).
B. The sky from a site: how many satellites are above the horizon at once, and how many are
   sunlit (observable with a telescope) during astronomical darkness.

Run from the repo root with the snapshot in data/raw:  python -m findings.sky_and_drag
"""
import time
from pathlib import Path
from datetime import datetime
import numpy as np, pandas as pd
from debris.tle_parser import split_tle_text, parse
from debris.config import RAW_DIR
from debris.propagator import propagate_many, time_grid, gmst_rad
df=pd.DataFrame([parse(l1,l2,n) for n,l1,l2 in split_tle_text((RAW_DIR / "active.tle").read_text())])
df=df[df.epoch>pd.Timestamp("2026-10-10")]
leo=df[df.apogee_km<2000]
# 1 altitude bands (space weather)
mean_alt=(leo.perigee_km+leo.apogee_km)/2
print("active",len(df),"LEO",len(leo))
for lo,hi in [(0,400),(400,450),(450,500),(500,550),(550,600),(600,2000)]:
    m=(mean_alt>=lo)&(mean_alt<hi); print(f"{lo}-{hi}",m.sum(),"starlink",leo[m].name.str.startswith("STARLINK").sum())
# 2/3 visibility from sites
START=datetime(2026,10,24,0,0); offs=np.arange(0,86400,60.0); jd,fr=time_grid(START,offs); g=gmst_rad(jd+fr)
t=time.time()
r,_,ok=propagate_many(df.tle_line1.tolist(),df.tle_line2.tolist(),jd,fr)
print("propagated",r.shape,f"{time.time()-t:.1f}s")
c,s=np.cos(g),np.sin(g)
X=c[None]*r[...,0]+s[None]*r[...,1]; Y=-s[None]*r[...,0]+c[None]*r[...,1]; Z=r[...,2]
# sun direction (low precision) in ECEF
jdf=jd+fr; n=jdf-2451545.0; L=np.radians((280.46+0.9856474*n)%360); M=np.radians((357.528+0.9856003*n)%360)
lam=L+np.radians(1.915)*np.sin(M)+np.radians(0.02)*np.sin(2*M); eps=np.radians(23.439)
sx,sy,sz=np.cos(lam),np.cos(eps)*np.sin(lam),np.sin(eps)*np.sin(lam)
SX=c*sx+s*sy; SY=-s*sx+c*sy; SZ=sz
def site(name,lat,lon,mask):
    la,lo=np.radians(lat),np.radians(lon); p=6378.137*np.array([np.cos(la)*np.cos(lo),np.cos(la)*np.sin(lo),np.sin(la)]); u=p/np.linalg.norm(p)
    dx,dy,dz=X-p[0],Y-p[1],Z-p[2]; rng=np.sqrt(dx**2+dy**2+dz**2)
    el=np.degrees(np.arcsin((dx*u[0]+dy*u[1]+dz*u[2])/rng))
    above=(el>mask)&ok
    sunel=np.degrees(np.arcsin(SX*u[0]+SY*u[1]+SZ*u[2]))
    # satellite sunlit: not in Earth's cylindrical shadow
    dot=X*SX+Y*SY+Z*SZ; perp=np.sqrt(np.maximum(X**2+Y**2+Z**2-dot**2,0))
    lit=(dot>0)|(perp>6378.137)
    star=df.name.str.startswith("STARLINK").values[:,None]
    ow=df.name.str.startswith("ONEWEB").values[:,None]
    cnt=above.sum(0)
    dark=sunel<-18
    obs=(above&lit).sum(0)
    print(name,"avg above",round(cnt.mean()),"max",cnt.max(),"starlink share",round((above&star).sum()/above.sum(),3),"oneweb",round((above&ow).sum()/above.sum(),3),
          "| dark minutes",dark.sum(),"avg sunlit visible in astro-dark",round(obs[dark].mean(),1) if dark.any() else None,"unique sunlit-visible in dark night",int(((above&lit)[:,dark]).any(1).sum()) if dark.any() else None)
site("Mumbai 10deg",19.08,72.88,10)
site("Svalbard 10deg",78.23,15.41,10)
site("New Mexico (dark site) 20deg",32.9,-105.5,20)
site("Toronto 10deg",43.65,-79.38,10)
