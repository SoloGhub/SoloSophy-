#!/usr/bin/env python3
"""Convert the CME research engine output (v0.3) into the web-app Engine Lab JSON.
Nothing is filtered: every state, observation, rule test, fold, zone and scenario is carried over.
Usage: python3 scripts/build_engine_lab.py <engine_output.json> <coverage_matrix.json> <out.json>
"""
import json, sys

TF_AR = {'daily': 'يومي', 'hourly': 'ساعة', 'thirty_minute': '30 دقيقة'}
STATE_AR = {
    'trend_down_weak': 'اتجاه هابط ضعيف', 'trend_down_strong': 'اتجاه هابط قوي',
    'trend_up_weak': 'اتجاه صاعد ضعيف', 'trend_up_strong': 'اتجاه صاعد قوي',
    'range_or_low_trend_strength': 'نطاق عرضي / اتجاه ضعيف', 'unclear_transition': 'مرحلة انتقالية غير واضحة',
    'NO_ANALYSIS': 'لا تحليل (البيانات في الحجر)',
}
VOL_AR = {'compression': 'انضغاط تقلّب', 'normal_relative_to_sample': 'تقلّب طبيعي مقارنةً بالعيّنة',
          'expansion': 'اتساع تقلّب'}
RULE_AR = {'trend_following_baseline': 'تتبّع الاتجاه', 'mean_reversion_baseline': 'العودة للمتوسط',
           'breakout_baseline': 'الاختراق', 'regime_conditioned_baseline': 'مشروط بالنظام السوقي'}
EDGE_AR = {'edge_not_established': 'لا أفضلية مثبتة', 'insufficient_active_signals': 'إشارات غير كافية',
           'negative_edge': 'أفضلية سلبية', 'edge_candidate': 'أفضلية مرشّحة'}
CONS_AR = {'partial_down_alignment': 'توافق هبوطي جزئي', 'partial_up_alignment': 'توافق صعودي جزئي',
           'full_down_alignment': 'توافق هبوطي كامل', 'full_up_alignment': 'توافق صعودي كامل',
           'no_alignment': 'لا توافق', 'mixed': 'متضارب'}
DIR_AR = {'down': 'هابط', 'up': 'صاعد', 'neutral': 'محايد', 'unavailable': 'غير متاح'}


def r(x, n=4):
    return None if x is None else round(x, n)


def stats(block):
    if not block:
        return None
    return dict(eligible=block.get('eligible_bars'), signals=block.get('active_signals'),
                coverage=r(block.get('signal_coverage')), hit=r(block.get('directional_hit_rate')),
                lo=r(block.get('hit_rate_wilson_low')), hi=r(block.get('hit_rate_wilson_high')),
                avg_ret=r(block.get('average_signed_forward_return'), 5),
                med_ret=r(block.get('median_signed_forward_return'), 5),
                edge=block.get('edge_status'), edge_ar=EDGE_AR.get(block.get('edge_status'), block.get('edge_status')))


def main(src, cov, out):
    e = json.load(open(src))
    cm = json.load(open(cov))
    lab = dict(schema='solosophy.engine_lab.v1', engine='CME Engine v0.3 (audited research)',
               generated_at_utc=e['generated_at_utc'], run_status=e['run_status'],
               ruleset_version=e['ruleset_version'], ruleset_validated=e['ruleset_validated'],
               probabilities_withheld=e['probabilities_withheld'],
               input_fingerprint=e['input_fingerprint'], ruleset_fingerprint=e['ruleset_fingerprint'],
               coverage=[dict(dataset=c['dataset_id'], decision=c['decision'], blocking=c['blocking_reasons'],
                              warnings=c.get('warnings', [])) for c in cm],
               assets={})
    for a, tfs in e['timeframe_states'].items():
        A = dict(timeframes={}, consensus=None, rules={}, zones={}, scenarios={}, time_profiles={},
                 action=e['operational_actions'].get(a))
        for tf, s in tfs.items():
            A['timeframes'][tf] = dict(tf_ar=TF_AR[tf], state=s.get('state'), state_ar=STATE_AR.get(s.get('state'), s.get('state')),
                                       volatility=s.get('volatility_state'), volatility_ar=VOL_AR.get(s.get('volatility_state'), s.get('volatility_state')),
                                       data_cutoff_utc=s.get('data_cutoff_utc'), quality=s.get('quality_decision'),
                                       observations={k: r(v, 4) for k, v in (s.get('observations') or {}).items()},
                                       live_blocking=s.get('live_blocking_reasons') or s.get('reason'))
        mc = e['multitimeframe_consensus'].get(a)
        if mc:
            A['consensus'] = dict(dirs={k: dict(v=v, ar=DIR_AR.get(v, v)) for k, v in mc['timeframe_directions'].items()},
                                  value=mc['consensus'], ar=CONS_AR.get(mc['consensus'], mc['consensus']))
        for tf, cv in e['candidate_rule_validation'].get(a, {}).items():
            rules = []
            for name, rep in cv['candidate_reports'].items():
                if 'horizons' not in rep:
                    continue
                for hk, h in rep['horizons'].items():
                    if 'development' in h:
                        rules.append(dict(rule=name, rule_ar=RULE_AR.get(name, name), kind='split', horizon=int(hk),
                                          decision=rep.get('current_ruleset_decision'),
                                          dev=stats(h.get('development')), holdout=stats(h.get('holdout'))))
            wf = cv.get('regime_conditioned_walk_forward', {})
            folds = []
            for hk, h in (wf.get('horizons') or {}).items():
                for f in h.get('folds', []):
                    folds.append(dict(horizon=int(hk), fold=f['fold'], test_start=f['test_start_utc'][:10],
                                      test_end=f['test_end_utc'][:10], **(stats(f.get('holdout')) or {})))
            A['rules'][tf] = dict(survivors=cv.get('survivors', []), rules=rules, walk_forward=dict(
                status=wf.get('status'), stable_edge_horizons=wf.get('stable_edge_horizons'),
                blockers=wf.get('calibration_blockers'), folds=folds))
        for tf, z in e['level_zones'].get(a, {}).items():
            A['zones'][tf] = [dict(low=r(x['low'], 3), high=r(x['high'], 3), centre=r(x['centre'], 3),
                                   evidence=x['evidence'], n=x['evidence_count']) for x in z['zones']]
        for tf, sc in e['scenario_set'].get(a, {}).items():
            A['scenarios'][tf] = [dict(scenario=x['scenario'], regime=x['regime'],
                                       trigger=x['trigger'], invalidation=x['invalidation'],
                                       zone=x['reference_zone'], probability=x['probability'],
                                       status=x['probability_status']) for x in sc]
        for tf, tp in e['time_profiles'].get(a, {}).items():
            hrs = [h for h in tp['by_hour'] if h.get('sample')]
            A['time_profiles'][tf] = dict(by_hour=[dict(h=h['hour_utc'], n=h['sample'], mean=r(h['mean_return'], 6),
                                                        med=r(h['median_return'], 6)) for h in hrs],
                                          by_weekday=tp['by_weekday'])
        lab['assets'][a] = A
    lab['journal'] = e.get('signal_journal', {}).get('integrity')
    lab['outcome_scoring'] = {k: v for k, v in e.get('outcome_scoring', {}).items() if k != 'integrity'}
    lab['layers'] = dict(event=e['event_layer']['status'], execution=e['execution_layer']['status'],
                         cross_asset=e['cross_asset_daily'], shadow=e['shadow_mode'])
    json.dump(lab, open(out, 'w'), ensure_ascii=False, indent=1)
    print('engine lab written', out, 'assets', list(lab['assets']))


if __name__ == '__main__':
    main(*sys.argv[1:])
