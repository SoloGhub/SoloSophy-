#!/usr/bin/env python3
"""SoloSophy — technical levels from IBKR daily bars (Last price, never settlement).
Usage: python3 scripts/compute_levels.py <raw_daily_dir> <out_json> [snapshot_json]
Raw files: <asset>_daily_long.json in engine raw format {request, response:{time,open,high,low,close,volume}}.
"""
import json, math, sys, statistics as st
from pathlib import Path

SPEC = {
  'GC':  dict(name='الذهب', contract='GCZ6', tick=0.10,   round_unit=0.5,   dec=1, exch='COMEX', unit='$/oz'),
  'SI':  dict(name='الفضة', contract='SIZ6', tick=0.005,  round_unit=0.05,  dec=3, exch='COMEX', unit='$/oz'),
  'HG':  dict(name='النحاس', contract='HGZ6', tick=0.0005, round_unit=0.005, dec=4, exch='COMEX', unit='$/lb'),
  'CL':  dict(name='النفط الخام WTI', contract='CLZ6', tick=0.01, round_unit=0.05, dec=2, exch='NYMEX', unit='$/bbl'),
  'SOXL':dict(name='SOXL (أشباه الموصلات ×3)', contract='SOXL', tick=0.01, round_unit=0.05, dec=2, exch='ARCA', unit='$'),
}

def clean(r):
    rows=[]
    for i,t in enumerate(r['time']):
        o,h,l,c,v=r['open'][i],r['high'][i],r['low'][i],r['close'][i],r['volume'][i]
        ok = l<=min(o,c)+1e-9 and h>=max(o,c)-1e-9 and v>0
        rows.append(dict(t=t,o=o,h=h,l=l,c=c,v=v,ok=ok))
    return rows

def last_clean_run(rows):
    # longest suffix without a bad bar
    k=len(rows)
    while k>0 and rows[k-1]['ok']: k-=1
    return rows[k:]

def sma(x,n): return sum(x[-n:])/n if len(x)>=n else None
def ema_series(x,n):
    k=2/(n+1); e=[x[0]]
    for v in x[1:]: e.append(v*k+e[-1]*(1-k))
    return e
def rsi(c,n=14):
    g=[max(c[i]-c[i-1],0) for i in range(1,len(c))]; d=[max(c[i-1]-c[i],0) for i in range(1,len(c))]
    ag=sum(g[:n])/n; ad=sum(d[:n])/n
    for i in range(n,len(g)): ag=(ag*(n-1)+g[i])/n; ad=(ad*(n-1)+d[i])/n
    return 100 if ad==0 else 100-100/(1+ag/ad)
def atr(rows,n=14):
    tr=[rows[0]['h']-rows[0]['l']]
    for i in range(1,len(rows)):
        tr.append(max(rows[i]['h']-rows[i]['l'],abs(rows[i]['h']-rows[i-1]['c']),abs(rows[i]['l']-rows[i-1]['c'])))
    a=sum(tr[1:n+1])/n
    for v in tr[n+1:]: a=(a*(n-1)+v)/n
    return a
def adx(rows,n=14):
    pdm=[];mdm=[];tr=[]
    for i in range(1,len(rows)):
        up=rows[i]['h']-rows[i-1]['h']; dn=rows[i-1]['l']-rows[i]['l']
        pdm.append(up if up>dn and up>0 else 0); mdm.append(dn if dn>up and dn>0 else 0)
        tr.append(max(rows[i]['h']-rows[i]['l'],abs(rows[i]['h']-rows[i-1]['c']),abs(rows[i]['l']-rows[i-1]['c'])))
    s_tr=sum(tr[:n]); s_p=sum(pdm[:n]); s_m=sum(mdm[:n]); dx=[]
    for i in range(n,len(tr)):
        s_tr=s_tr-s_tr/n+tr[i]; s_p=s_p-s_p/n+pdm[i]; s_m=s_m-s_m/n+mdm[i]
        pdi=100*s_p/s_tr; mdi=100*s_m/s_tr; dx.append((100*abs(pdi-mdi)/(pdi+mdi)) if pdi+mdi else 0)
    a=sum(dx[:n])/n
    for v in dx[n:]: a=(a*(n-1)+v)/n
    return a,pdi,mdi

def rtick(p,spec,mode='nearest',away=0):
    t=spec['tick']; q=p/t
    q = math.floor(q+1e-9) if mode=='down' else math.ceil(q-1e-9) if mode=='up' else round(q)
    v=q*t
    ru=spec['round_unit']
    if abs(v/ru-round(v/ru))<1e-6 and away!=0:  # avoid crowded round prices
        v+=away*t
    return round(v,spec['dec'])

def pivots(h,l,c):
    p=(h+l+c)/3; r=h-l
    return dict(P=p,R1=2*p-l,S1=2*p-h,R2=p+r,S2=p-r,R3=h+2*(p-l),S3=l-2*(h-p),
                fR1=p+0.382*r,fR2=p+0.618*r,fR3=p+r,fS1=p-0.382*r,fS2=p-0.618*r,fS3=p-r)

def main(raw_dir,out,snap_path=None):
    snaps=json.load(open(snap_path)) if snap_path else {}
    res={}
    for a,spec in SPEC.items():
        r=json.load(open(Path(raw_dir)/f'{a.lower()}_daily_long.json'))['response']
        rows=last_clean_run(clean(r))
        c=[x['c'] for x in rows]
        last=rows[-1]; prev=rows[-2]
        # trading week = last 5 sessions
        wk=rows[-5:]; prior_fri=rows[-6]['c']
        wh=max(x['h'] for x in wk); wl=min(x['l'] for x in wk)
        e12=ema_series(c,12); e26=ema_series(c,26); macd=[x-y for x,y in zip(e12,e26)]; sig=ema_series(macd,9)
        a14=atr(rows); ad,pdi,mdi=adx(rows)
        s20=sma(c,20); sd20=st.pstdev(c[-20:])
        iv=snaps.get(a,{}).get('iv')
        wk_sigma = last['c']*iv*math.sqrt(5/252) if iv else None
        dp=pivots(last['h'],last['l'],last['c']); wp=pivots(wh,wl,last['c'])
        d=dict(asset=a,**spec,bars_used=len(rows),first_bar=rows[0]['t'],last_bar=last['t'],
          close=last['c'],prev_close=prev['c'],day_chg_pct=100*(last['c']/prev['c']-1),
          week_open_ref=prior_fri,week_chg_pct=100*(last['c']/prior_fri-1),week_high=wh,week_low=wl,
          m1_chg_pct=100*(last['c']/rows[-22]['c']-1) if len(rows)>22 else None,
          sma20=s20,sma50=sma(c,50),sma100=sma(c,100),sma200=sma(c,200),ema12=e12[-1],ema26=e26[-1],
          macd=macd[-1],macd_signal=sig[-1],macd_hist=macd[-1]-sig[-1],macd_hist_prev=macd[-2]-sig[-2],
          rsi14=rsi(c),atr14=a14,atr_pct=100*a14/last['c'],adx14=ad,plus_di=pdi,minus_di=mdi,
          bb_up=s20+2*sd20,bb_dn=s20-2*sd20,bb_pctb=(last['c']-(s20-2*sd20))/(4*sd20) if sd20 else None,
          hi20=max(x['h'] for x in rows[-20:]),lo20=min(x['l'] for x in rows[-20:]),
          hi60=max(x['h'] for x in rows[-60:]),lo60=min(x['l'] for x in rows[-60:]),
          hi_all=max(x['h'] for x in rows[-250:]),lo_all=min(x['l'] for x in rows[-250:]),
          iv_annual=iv,week_1sigma=wk_sigma,
          range_1s=[last['c']-wk_sigma,last['c']+wk_sigma] if wk_sigma else None,
          range_2s=[last['c']-2*wk_sigma,last['c']+2*wk_sigma] if wk_sigma else None,
          pivots_daily=dp,pivots_weekly=wp)
        def sdate(t):
            # futures daily bars are stamped at the session open (22:00/23:00Z the evening before) -> label by session date
            import datetime as _dt
            d0=_dt.datetime.fromisoformat(t.replace('Z','+00:00'))
            if a!='SOXL': d0=d0+_dt.timedelta(hours=4)
            return d0.date().isoformat()
        d['spark']=[dict(t=sdate(x['t']),o=x['o'],h=x['h'],l=x['l'],c=x['c']) for x in rows[-90:]]
        d['last_session']=sdate(last['t'])
        res[a]=d
    json.dump(res,open(out,'w'),ensure_ascii=False,indent=1)
    for a,d in res.items():
        print(f"{a}: close {d['close']} d {d['day_chg_pct']:+.2f}% w {d['week_chg_pct']:+.2f}% bars {d['bars_used']} "
              f"sma20 {d['sma20']:.4g} sma50 {d['sma50']:.4g} sma200 {d['sma200'] and round(d['sma200'],4)} rsi {d['rsi14']:.1f} "
              f"atr {d['atr14']:.4g} ({d['atr_pct']:.2f}%) adx {d['adx14']:.1f} +di {d['plus_di']:.1f} -di {d['minus_di']:.1f} "
              f"macdh {d['macd_hist']:.4g} (prev {d['macd_hist_prev']:.4g}) bb {d['bb_dn']:.4g}-{d['bb_up']:.4g} "
              f"wkHL {d['week_high']}-{d['week_low']} 1s {d['week_1sigma'] and round(d['week_1sigma'],4)} hi60 {d['hi60']} lo60 {d['lo60']}")
        print('   weekly piv', {k:round(v,spec['dec'] if False else 4) for k,v in d['pivots_weekly'].items()})

if __name__=='__main__':
    main(*sys.argv[1:])
