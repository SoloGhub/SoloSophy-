from __future__ import annotations

import base64
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import traceback

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "SoloSophy_Audited_Research.ipynb"


def markdown(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}


def execute(cells: list[dict]) -> None:
    namespace: dict = {"__name__": "__main__"}
    execution_count = 0
    for cell in cells:
        if cell["cell_type"] != "code":
            continue
        execution_count += 1
        source = "".join(cell["source"])
        stream = io.StringIO()
        try:
            with redirect_stdout(stream), redirect_stderr(stream):
                exec(compile(source, f"notebook-cell-{execution_count}", "exec"), namespace)
        except Exception:
            stream.write(traceback.format_exc())
            raise
        outputs: list[dict] = []
        if stream.getvalue():
            outputs.append({"output_type": "stream", "name": "stdout", "text": stream.getvalue().splitlines(keepends=True)})
        for figure_number in plt.get_fignums():
            buffer = io.BytesIO()
            plt.figure(figure_number).savefig(buffer, format="png", dpi=120, bbox_inches="tight")
            outputs.append({"output_type": "display_data", "metadata": {}, "data": {"image/png": base64.b64encode(buffer.getvalue()).decode("ascii")}})
        plt.close("all")
        cell["execution_count"] = execution_count
        cell["outputs"] = outputs


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    cells = [
        markdown(
            "# SoloSophy — تدقيق جودة البيانات والتحقق الزمني\n\n"
            "## الخلاصة التنفيذية\n\n"
            "هذا الدفتر يعيد قراءة مخرجات المحرك الفعلية، ويفحص تغطية البيانات، "
            "ونتيجة الاختبار المتحرك خارج العينة، وسلامة سجل الإشارات. لا توجد بيانات مصطنعة."
        ),
        markdown(
            "## السياق والمنهج\n\n"
            "- المصدر: الاستجابات المحفوظة من اتصال IBKR لعقود GC وSI.\n"
            "- الأطر: يومي، ساعة، وثلاثون دقيقة.\n"
            "- التحقق: فحص زمني رجعي بقواعد ثابتة، مع استبعاد العوائد المتداخلة ونهايات النوافذ؛ لا يمثل عينة جديدة لم تُمس.\n"
            "- الحسابات تُنفذ تسلسليًا في بايثون؛ هذا البناء لا يشغّل نواة جوبيتر في البيئة الحالية.\n"
            "- بوابة النشر: لا احتمالات قبل ثبات ميزة موجبة وإضافة التكاليف ومحاكاة التنفيذ وعينة مستقبلية."
        ),
        code(
            "from pathlib import Path\nimport json\nimport matplotlib.pyplot as plt\nimport pandas as pd\n\n"
            "ROOT = Path.cwd()\nif not (ROOT / 'reports' / 'audited').exists():\n    ROOT = ROOT.parent\n"
            "REPORT = ROOT / 'reports' / 'audited'\ncoverage = pd.read_csv(REPORT / 'coverage_matrix.csv')\n"
            "engine = json.loads((REPORT / 'engine_output.json').read_text(encoding='utf-8'))\n"
            "assert set(coverage['symbol']) == {'GC', 'SI'}\nassert engine['probabilities_withheld'] is True\n"
            "print('Ruleset:', engine['ruleset_version'])"
        ),
        markdown("## البيانات وجودتها"),
        code(
            "columns = ['symbol', 'timeframe', 'bar_count', 'analysis_bar_count', 'research_eligible', 'live_eligible', 'quarantine_count', "
            "'long_history_price_quality', 'volume_quality', 'decision']\n"
            "coverage_view = coverage[columns].sort_values(['symbol', 'timeframe']).reset_index(drop=True)\n"
            "print(coverage_view.to_string(index=False))"
        ),
        code(
            "plot_coverage = coverage.copy()\nplot_coverage['eligible_bars'] = plot_coverage['analysis_bar_count'].where(plot_coverage['research_eligible'], 0)\n"
            "pivot = plot_coverage.pivot(index='timeframe', columns='symbol', values='eligible_bars')\n"
            "ax = pivot.plot(kind='bar', figsize=(9, 4), color=['#B8892E', '#7A8798'])\n"
            "ax.set_title('Usable analysis bars after quality gates')\nax.set_ylabel('Bars'); ax.set_xlabel('Timeframe'); ax.grid(axis='y', alpha=.25)\n"
            "plt.tight_layout(); plt.show()"
        ),
        markdown("## نتائج المشي الزمني خارج العينة"),
        code(
            "rows = []\nfor asset, timeframes in engine['candidate_rule_validation'].items():\n"
            "    for timeframe, comparison in timeframes.items():\n        wf = comparison['regime_conditioned_walk_forward']\n"
            "        for horizon, detail in wf['horizons'].items():\n            pooled = detail['pooled_holdout']\n"
            "            rows.append({'asset': asset, 'timeframe': timeframe, 'horizon_bars': int(horizon), "
            "'active_signals': pooled['active_signals'], 'hit_rate': pooled['directional_hit_rate'], "
            "'wilson_low': pooled['hit_rate_wilson_low'], 'average_signed_return': pooled['average_signed_forward_return'], "
            "'edge_status': pooled['edge_status'], 'stable_positive_edge': detail.get('stable_positive_edge', False)})\n"
            "walk_forward = pd.DataFrame(rows).sort_values(['asset', 'timeframe', 'horizon_bars'])\n"
            "print(walk_forward.to_string(index=False))\nassert not walk_forward['stable_positive_edge'].any()"
        ),
        code(
            "plot_rows = walk_forward.dropna(subset=['hit_rate']).copy()\n"
            "plot_rows['label'] = plot_rows['asset'] + ' · ' + plot_rows['timeframe'] + ' · ' + plot_rows['horizon_bars'].astype(str)\n"
            "fig, ax = plt.subplots(figsize=(10, 6))\ncolors = ['#2F6B5F' if value >= .5 else '#A34A3A' for value in plot_rows['hit_rate']]\n"
            "ax.scatter(plot_rows['active_signals'], plot_rows['hit_rate'], c=colors, s=55)\n"
            "ax.axhline(.5, color='#555', linestyle='--', linewidth=1)\n"
            "for _, row in plot_rows.iterrows():\n    ax.annotate(row['label'], (row['active_signals'], row['hit_rate']), fontsize=7, xytext=(4, 4), textcoords='offset points')\n"
            "ax.set_title('Walk-forward hit rate versus active-signal sample')\n"
            "ax.set_xlabel('Active signals'); ax.set_ylabel('Directional hit rate'); ax.grid(alpha=.2)\nplt.tight_layout(); plt.show()"
        ),
        markdown("## سجل الإشارات والوضع المستقبلي"),
        code(
            "journal_lines = (REPORT / 'signal_journal.jsonl').read_text(encoding='utf-8').splitlines()\n"
            "journal = [json.loads(line) for line in journal_lines if line.strip()]\n"
            "summary = {'journal_records': len(journal), 'journal_integrity': engine['signal_journal']['integrity'], "
            "'shadow_mode': engine['shadow_mode'], 'walk_forward_survivors': engine['walk_forward_survivors']}\n"
            "print(json.dumps(summary, ensure_ascii=False, indent=2))\nassert engine['signal_journal']['integrity']['valid'] is True"
        ),
        markdown(
            "## الاستنتاجات\n\n"
            "- فحوص السعر الداخلية وحدها لا تكفي للاعتماد الحي؛ الفواصل الزمنية وبنية السلسلة غير متحقق منهما.\n"
            "- التاريخ اليومي الطويل يحتوي شواذ بنيوية؛ التحليل يستخدم فقط الجزء الموثوق بعد آخر شذوذ.\n"
            "- لا يوجد إثبات لميزة موجبة مستقرة؛ الاختبار رجعي على تاريخ سبق فحصه، وليس تحققًا مستقبليًا مستقلًا.\n"
            "- اليومي للفضة محجوز لأن الجزء الصالح لا يبلغ الحد الأدنى؛ لا يستخدم في دمج اتجاه يومي أو ارتباط يومي.\n"
            "- السيناريوهات الحالية وصفية ومشروطة بمستويات مقاسة، من دون احتمال أو أمر تداول.\n"
            "- السجل مخصص للملاحظات البحثية فقط، ويكشف العبث المعتاد ولا يمثل تشفيرًا أو حماية مطلقة من إعادة كتابة الملف كله."
        ),
    ]
    previous_cwd = Path.cwd()
    try:
        os.chdir(ROOT)
        execute(cells)
    finally:
        os.chdir(previous_cwd)
    for index, cell in enumerate(cells):
        cell['id'] = f'audit-cell-{index}'
    notebook = {"cells": cells, "metadata": {"execution_method": 'sequential_python_exec_not_jupyter_kernel', "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}}, "nbformat": 4, "nbformat_minor": 5}
    OUTPUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
