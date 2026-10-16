#!/usr/bin/env python3
"""SoloSophy report kit — every number in a report is computed here, never typed by hand.

Typical use inside a scheduled run (see ops/RUNBOOK.md):
    from report_kit import Kit
    K = Kit('2026-10-19')                     # reads data/derived/<date>/levels.json + data/raw/<date>/snapshots.json
    lad = K.ladder('GC', [14,24,28,21,13], [why1..why5])
    st  = K.setup('GC','long','pullback', entry_level, stop_level, [t1,t2], label, condition, note)
    a   = K.asset('GC', where=..., tag='range', tag_ar=..., control=..., drivers=..., ladder=lad, setups=[...], stance=..., analysts=[...])
    K.write(report_dict, slot='pre_us')      # writes docs/data/reports/<date>/<slot>.json and updates docs/data/index.json
"""
import json, datetime, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from setups import build, to_tick, SPEC  # noqa: E402

BASE = [16, 22, 24, 22, 16]          # normal split at ±0.3σ / ±1σ (rounded)
LADDER_NAMES = ['صعود قوي', 'صعود معتدل', 'تذبذب عرضي', 'هبوط معتدل', 'هبوط قوي']
LADDER_KEYS = ['strong_up', 'mild_up', 'range', 'mild_down', 'strong_down']
SLOT_AR = {'weekly': 'التقرير الأسبوعي', 'pre_europe': 'لقطة ما قبل أوروبا', 'pre_us': 'تقرير ما قبل الجلسة الأمريكية',
           'us_mid': 'لقطة منتصف الجلسة الأمريكية', 'pre_asia': 'تقرير ما قبل آسيا', 'on_demand': 'تقرير عند الطلب',
           'alert_t30': 'تنبيه قبل الحدث (T-30)', 'alert_t1': 'تنبيه بعد الحدث (T+1)'}
FAMILY = {'GC': 'gc', 'SI': 'si', 'HG': 'hg', 'CL': 'cl', 'SOXL': 'soxl'}


def fnum(asset, x):
    return f"{x:,.{SPEC[asset]['dec']}f}"


class Kit:
    def __init__(self, date):
        self.date = date
        self.L = json.load(open(ROOT / f'data/derived/{date}/levels.json'))
        sp = ROOT / f'data/raw/{date}/snapshots.json'
        self.SNAP = json.load(open(sp)) if sp.exists() else {}

    # ---------------- scenario ladder (analytical weighting, declared method)
    def ladder(self, asset, weights, why, horizon='الأسبوع الحالي (إغلاق الجمعة)', days=5):
        assert len(weights) == 5 and sum(weights) == 100, f'{asset}: weights must be 5 and sum to 100'
        assert all(abs(a - b) <= 8 for a, b in zip(weights, BASE)), f'{asset}: tilt > 8 points vs base {BASE}'
        d = self.L[asset]
        c, iv = d['close'], d['iv_annual']
        s = c * iv * math.sqrt(days / 252)
        dec = SPEC[asset]['dec']
        b = [c + s, c + 0.3 * s, c - 0.3 * s, c - s]
        rng = [f"فوق {fnum(asset, b[0])}", f"{fnum(asset, b[1])} – {fnum(asset, b[0])}", f"{fnum(asset, b[2])} – {fnum(asset, b[1])}",
               f"{fnum(asset, b[3])} – {fnum(asset, b[2])}", f"تحت {fnum(asset, b[3])}"]
        items = [dict(key=LADDER_KEYS[i], name=LADDER_NAMES[i], weight=weights[i], base=BASE[i], tilt=weights[i] - BASE[i],
                      range=rng[i], why=why[i]) for i in range(5)]
        return dict(items=items, up_total=weights[0] + weights[1], range_total=weights[2], down_total=weights[3] + weights[4],
                    sigma=round(s, dec + 1), iv=round(100 * iv, 1), days=days,
                    one_sigma=[round(c - s, dec), round(c + s, dec)], two_sigma=[round(c - 2 * s, dec), round(c + 2 * s, dec)],
                    horizon=horizon, ntz=[round(b[2], dec), round(b[1], dec)])

    def setup(self, asset, side, kind, entry_level, stop_level, targets, label, condition, note=''):
        return build(asset, self.L[asset]['atr14'], side, kind, entry_level, stop_level, targets, label, condition, note)

    # ---------------- indicator table with plain-language meaning
    def indicator_rows(self, a):
        d = self.L[a]
        c = d['close']
        rows = []

        def ma(name, v):
            if v is None:
                return [name, 'غير متاح', 'سجل العقد قبل 200 جلسة كان ضعيف السيولة (بيانات غير موثوقة) — لا يُحسب']
            gap = 100 * (c / v - 1)
            side = 'فوق' if gap > 0 else 'تحت'
            role = 'دعم ديناميكي' if gap > 0 else 'مقاومة ديناميكية'
            return [name, fnum(a, v), f"السعر {side}ه بـ {abs(gap):.2f}% ← يعمل كـ{role}"]
        rows += [ma('متوسط 20 يوماً', d['sma20']), ma('متوسط 50 يوماً', d['sma50']), ma('متوسط 200 يوم', d['sma200'])]
        r = d['rsi14']
        rows.append(['RSI (14)', f"{r:.1f}", 'تشبّع شرائي — خطر جني أرباح' if r >= 70 else 'تشبّع بيعي — احتمال ارتداد فني' if r <= 30 else 'منطقة ضعف (دون 50)' if r < 50 else 'منطقة قوة (فوق 50)'])
        h, hp = d['macd_hist'], d['macd_hist_prev']
        mm = ('إيجابي ومتسارع' if h > hp else 'إيجابي لكن يتباطأ') if h > 0 else ('سلبي لكن يتحسّن' if h > hp else 'سلبي ويتسارع')
        rows.append(['MACD (هيستوجرام)', f"{h:+.4g}", f"زخم {mm} (السابق \u2066{hp:+.4g}\u2069)"])
        ad = d['adx14']
        am = 'اتجاه قوي' if ad >= 25 else 'اتجاه ضعيف/نطاق' if ad < 20 else 'اتجاه في طور التكوين'
        dom = 'البائعون مسيطرون (−DI > +DI)' if d['minus_di'] > d['plus_di'] else 'المشترون مسيطرون (+DI > −DI)'
        rows.append(['ADX (14)', f"{ad:.1f}", f"{am} — {dom}"])
        rows.append(['ATR (14)', f"{fnum(a, d['atr14'])} ({d['atr_pct']:.2f}%)", 'متوسط المدى اليومي — أساس إزاحة نقاط الدخول (10%) والوقف'])
        pb = d['bb_pctb']
        bm = 'عند/فوق الحد العلوي — امتداد' if pb >= 0.95 else 'عند/تحت الحد السفلي — امتداد هبوطي' if pb <= 0.05 else 'في النصف العلوي' if pb > 0.5 else 'في النصف السفلي'
        rows.append(['بولينجر (20، 2)', f"{fnum(a, d['bb_dn'])} – {fnum(a, d['bb_up'])}", f"\u2066%b = {pb:.2f}\u2069 ← {bm}"])
        iv = d['iv_annual']
        ivp = (self.SNAP.get(a) or {}).get('ivp_52w')
        ivm = f"تقلّب ضمني سنوي {100*iv:.1f}%"
        if ivp is not None:
            ivm += f" — مئين 52 أسبوعاً ≈ {100*ivp:.0f}% ({'رخيص نسبياً' if ivp < 0.3 else 'مرتفع نسبياً' if ivp > 0.7 else 'متوسط'})"
        rows.append(['IV (IBKR)', f"{100*iv:.1f}%", ivm])
        rows.append(['نطاق 1σ أسبوعي', f"{fnum(a, d['range_1s'][0])} – {fnum(a, d['range_1s'][1])}",
                     f"σ = {fnum(a, d['week_1sigma'])} (السعر × IV × √(5/252)) — نحو 68% من النتائج تاريخياً داخل هذا النطاق"])
        return rows

    # ---------------- descriptive historical analog from the same IBKR bars
    def weekly_series(self, asset):
        r = json.load(open(ROOT / f'data/raw/{self.date}/daily/{asset.lower()}_daily_long.json'))['response']
        rows = []
        for i, t in enumerate(r['time']):
            o, h, lo, c, v = r['open'][i], r['high'][i], r['low'][i], r['close'][i], r['volume'][i]
            ok = lo <= min(o, c) + 1e-9 and h >= max(o, c) - 1e-9 and v > 0
            d = datetime.datetime.fromisoformat(t.replace('Z', '+00:00'))
            if asset != 'SOXL':
                d = d + datetime.timedelta(hours=4)
            rows.append((d.date(), c, ok))
        k = len(rows)
        while k > 0 and rows[k - 1][2]:
            k -= 1
        rows = rows[k:]
        wk = {}
        for d, c, _ in rows:
            iso = d.isocalendar()
            wk[(iso[0], iso[1])] = (d, c)
        keys = sorted(wk)
        return [wk[x][0] for x in keys], [wk[x][1] for x in keys]

    def analog(self, asset, cond=None, label=None):
        dt, cl = self.weekly_series(asset)
        ret = [None] + [100 * (cl[i] / cl[i - 1] - 1) for i in range(1, len(cl))]
        cur = ret[-1]
        if cond is None:   # default: same direction, at least 60% of the current magnitude
            lo = 0.6 * cur
            cond = (lambda r: r >= lo) if cur >= 0 else (lambda r: r <= lo)
            label = label or (f"أسابيع {'صعد' if cur >= 0 else 'هبط'} فيها {asset} بنسبة {abs(lo):.2f}% أو أكثر")
        hits = [dict(week=str(dt[i]), ret=round(ret[i], 2), next=round(ret[i + 1], 2)) for i in range(1, len(cl) - 1) if cond(ret[i])]
        nxt = [h_['next'] for h_ in hits]
        res = dict(asset=asset, label=label, sample_weeks=len(cl) - 1, period=f"{dt[0]} → {dt[-1]}", n=len(hits), cases=hits[-8:])
        if nxt:
            s = sorted(nxt)
            res.update(next_up_share=round(100 * sum(1 for x in nxt if x > 0) / len(nxt)), next_median=round(s[len(s) // 2], 2),
                       next_min=round(min(nxt), 2), next_max=round(max(nxt), 2))
        return res

    # ---------------- assemble one asset block (adds every computed field)
    def asset(self, code, *, name, contract, unit, tag, tag_ar, where, control, drivers, ladder, setups, stance,
              analysts=None, positioning=None, analog=None, front=None):
        d = self.L[code]
        sn = self.SNAP.get(code) or {}
        a = dict(code=code, family=FAMILY[code], name=name, contract=contract, unit=unit, tag=tag, tag_ar=tag_ar, where=where,
                 control=control, drivers=drivers, ladder=ladder, setups=setups, stance=stance, analysts=analysts or [],
                 positioning=positioning)
        a['price'] = dict(last=d['close'], day=round(d['day_chg_pct'], 2), week=round(d['week_chg_pct'], 2),
                          month=round(d['m1_chg_pct'], 2) if d.get('m1_chg_pct') is not None else None,
                          week_high=d['week_high'], week_low=d['week_low'], prev_week_close=d['week_open_ref'],
                          oi=sn.get('oi'), volume=sn.get('volume'), iv=round(100 * d['iv_annual'], 1),
                          hv=round(100 * sn['hv30'], 1) if sn.get('hv30') else None, status=sn.get('status'), source='IBKR · Last')
        if front:
            a['price']['front'] = front
        a['indicators'] = self.indicator_rows(code)
        a['analog'] = analog or self.analog(code)
        a['spark'] = d['spark']
        a['ntz'] = ladder['ntz']
        a['atr'] = round(d['atr14'], SPEC[code]['dec'])
        return a

    # ---------------- write report + archive index
    def write(self, report, slot):
        out = ROOT / f'docs/data/reports/{self.date}'
        out.mkdir(parents=True, exist_ok=True)
        report.setdefault('schema', 'solosophy.report.v1')
        report.setdefault('type', slot)
        pref = next((k for k in ('on_demand', 'alert_watch', 'alert_t30', 'alert_t1') if slot.startswith(k)), slot)
        report.setdefault('type_ar', SLOT_AR.get(slot) or SLOT_AR.get(pref) or ('تنبيه حركة سعرية' if pref == 'alert_watch' else slot))
        report.setdefault('id', f'{self.date}-{slot}')
        path = out / f'{slot}.json'
        json.dump(report, open(path, 'w'), ensure_ascii=False, indent=1)
        idx_path = ROOT / 'docs/data/index.json'
        idx = json.load(open(idx_path)) if idx_path.exists() else dict(schema='solosophy.index.v1', reports=[])
        entry = dict(id=report['id'], date=self.date, type=slot, type_ar=report['type_ar'], title=report.get('subtitle', ''),
                     path=f'data/reports/{self.date}/{slot}.json', issued=report['issued_dubai'], headline=report.get('headline', ''))
        idx['reports'] = [r for r in idx['reports'] if r['id'] != entry['id']] + [entry]
        idx['reports'].sort(key=lambda r: r['issued'], reverse=True)
        idx['latest'] = idx['reports'][0]['path']
        idx['updated'] = report['issued_dubai']
        json.dump(idx, open(idx_path, 'w'), ensure_ascii=False, indent=1)
        return path
