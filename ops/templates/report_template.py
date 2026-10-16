#!/usr/bin/env python3
"""SoloSophy report template — copy to scripts/runs/build_<DATE>_<SLOT>.py, fill every TODO, run, then validate.

RULES (enforced by scripts/validate_report.py — a single error blocks publication):
  * Never type a price/indicator/percentage that the kit can compute. Prices come from levels.json (IBKR Last).
  * Text may quote numbers ONLY if they appear in levels.json, snapshots.json, or a cited source.
  * Ladder weights: 5 integers summing to 100, each within ±8 of the base 16/22/24/22/16.
  * Setups: pass chart LEVELS to K.setup(); the kit applies the 10%-ATR offset, tick rounding and crowded-price nudge.
  * Entries must be outside the no-trade zone (the ladder's middle rung).
  * Client-facing Arabic: formal, confident, never first person ("أنا/أرى/أعتقد" are forbidden). Solo Vision: Egyptian, confident, no "أنا".
  * Leave no "TODO" text — the validator rejects it.
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]   # works from scripts/runs/ and ops/templates/
sys.path.insert(0, str(ROOT / 'scripts'))
from report_kit import Kit, SLOT_AR  # noqa: E402

DATE = 'TODO-YYYY-MM-DD'        # Dubai date of issue, same as data/raw/<DATE>/
SLOT = 'TODO-slot'              # pre_europe | pre_us | us_mid | pre_asia | weekly | on_demand | alert_t30 | alert_t1
FULL = SLOT in ('pre_us', 'pre_asia', 'weekly')   # set FULL = True by hand for a full on-demand report
K = Kit(DATE)

def A(code, **kw):
    return K.asset(code, **kw)

# ---------------------------------------------------------------- assets (repeat for GC, SI, HG, CL, SOXL)
assets = [
    A('GC', name='الذهب', contract='GCZ6 · COMEX', unit='$/oz',
      tag='TODO bullish|bearish|range', tag_ar='TODO وصف قصير',
      where='TODO إحنا فين: 3–5 جمل — السعر، التغير، النطاق، المتوسطات، ماذا حدث في الجلسة/الأسبوع.',
      control=dict(resist=[('TODO 4,220.4', 'TODO وصف المستوى')], pivot=('TODO 4,174.7', 'المحور'),
                   support=[('TODO 4,167.5', 'TODO وصف المستوى')]),
      drivers=[('+', 'TODO عنوان', 'TODO شرح مع مصدر')],      # '+' / '−' / '±'
      ladder=K.ladder('GC', [16, 22, 24, 22, 16], ['TODO سبب صعود قوي', 'TODO', 'TODO', 'TODO', 'TODO'],
                      horizon='TODO مثلاً: جلسة اليوم حتى إغلاق نيويورك', days=1),   # days=1 for intraday/daily, 5 for weekly
      setups=[
          K.setup('GC', 'long', 'pullback', 0, 0, [0, 0], 'شراء الارتداد', 'TODO الشرط'),     # entry_level, stop_level, [t1, t2]
          K.setup('GC', 'short', 'rejection', 0, 0, [0, 0], 'بيع الرفض', 'TODO الشرط'),
      ],
      stance='TODO الخلاصة في جملة',
      analysts=[dict(source='TODO', country='TODO', date='TODO', view='TODO', url='https://TODO')] if FULL else [],
      positioning=None),   # full reports: dict like docs/data/reports/2026-10-17/weekly.json → assets[i].positioning
]

report = dict(
    type=SLOT, type_ar=SLOT_AR.get(SLOT, SLOT),
    title='SoloSophy Insights', edition='TODO e.g. Pre-US Edition',
    subtitle='TODO عنوان فرعي (التاريخ والجلسة)',
    issued_dubai='TODO 2026-10-19T15:20:00+04:00', issued_label='TODO الاثنين 19 أكتوبر 2026 · 15:20 بتوقيت دبي',
    data_cutoff='TODO أسعار IBKR (Last) حتى HH:MM دبي',
    slogan='The Art of Investment — When an Idea Transforms Your Entire Wealth',
    headline='TODO عنوان رئيسي واحد',
    what_changed=[dict(icon='x', text='TODO ما الذي تغيّر منذ التقرير السابق')],
    sessions=[],                       # optional: copy structure from the weekly report
    assets=assets,
    events=[dict(day='TODO', time='TODO', event='TODO', country='TODO', consensus='TODO', prior='TODO', imp='TODO حرج|مرتفع|متوسط', assets='TODO', alert=False)],
    solo_vision=['TODO فقرة مصرية واثقة بلا "أنا" — يمكن استخدام <b>…</b> للتأكيد'],
    solo_vision_wisdom='TODO الحكمة في سطر',
    methodology=['الأسعار: IBKR Last · المؤشرات من الشموع اليومية · السيناريوهات σ من IV · الإزاحة 10% ATR · منطقة اللاتداول = الخانة الوسطى.'],
    sources=[dict(title='بيانات الأسعار', url=None, note='Interactive Brokers (IBKR) — قراءة فقط', tier='A'),
             dict(title='TODO عنوان المصدر', url='https://TODO', note=None, tier='B')],
    disclaimer='هذا التقرير لأغراض المعلومات والتحليل فقط ولا يمثل عرضاً أو توصية شخصية بالشراء أو البيع. التداول بالعقود الآجلة والأدوات المضاعفة ينطوي على مخاطر مرتفعة قد تتجاوز رأس المال.',
    engine_ref='data/engine/2026-10-17.json',   # point to the newest docs/data/engine/<date>.json
    voice=[dict(title='الافتتاح', text='TODO نص للقراءة الصوتية — الأرقام تُكتب بالحروف لتُقرأ بشكل صحيح')],
)
if FULL:
    report.update(
        macro=dict(data=[], fed=[], rates=[], china=[]),            # TODO fill (see weekly.json for structure)
        geopolitics=dict(confirmed=[], unconfirmed=[]),               # confirmed = 2+ independent sources or official
        market_makers=dict(cot_note='', cot=[], etf=[], central_banks=[], options=[], options_note='', prediction=[], prediction_note=''),
        conflicts=[],                                                 # every conflicting number + how it was resolved
        events_after=[],
    )

path = K.write(report, SLOT)
print('written', path)
