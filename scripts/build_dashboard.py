import os, json
from supabase import create_client
from datetime import datetime, timezone, timedelta
from collections import defaultdict

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
KST = timezone(timedelta(hours=9))

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

res = supabase.table('maple_records') \
    .select('*') \
    .order('collected_at', desc=False) \
    .execute()

rows = res.data

def fmt_num(n):
    if n is None: return '-'
    n = int(n)
    if n >= 100000000: return f'{n/100000000:.2f}억'
    if n >= 10000:     return f'{n/10000:.1f}만'
    return f'{n:,}'

by_date = defaultdict(dict)
for r in rows:
    dt = datetime.fromisoformat(r['collected_at'])
    date_kst = dt.astimezone(KST).strftime('%Y-%m-%d')
    by_date[date_kst][r['nick']] = r

dates = sorted(by_date.keys(), reverse=True)
all_nicks = sorted(set(r['nick'] for r in rows))

chart_data = {}
for nick in all_nicks:
    chart_data[nick] = {
        'labels': [],
        'stat_equiv_380': [],
        'hexa_equiv_380': [],
        'level': [],
        'exp_pct': [],
    }
for r in rows:
    dt = datetime.fromisoformat(r['collected_at']).astimezone(KST)
    label = dt.strftime('%m/%d %H:%M')
    nick = r['nick']
    chart_data[nick]['labels'].append(label)
    chart_data[nick]['stat_equiv_380'].append(r.get('stat_equiv_380'))
    chart_data[nick]['hexa_equiv_380'].append(r.get('hexa_equiv_380'))
    chart_data[nick]['level'].append(r.get('level'))
    chart_data[nick]['exp_pct'].append(r.get('exp_pct'))

tab_btns = ''
tab_contents = ''
for di, date in enumerate(dates):
    active = 'active' if di == 0 else ''
    tab_btns += f'<button class="tab-btn {active}" onclick="showTab(\'{date}\')" id="btn-{date}">{date}</button>'

    day = by_date[date]
    prev_date = dates[di+1] if di+1 < len(dates) else None
    prev_day = by_date.get(prev_date, {})

    cards = ''
    for nick in all_nicks:
        d = day.get(nick)
        if not d:
            cards += f'<div class="card no-data"><div class="card-title">🍁 {nick}</div><div class="no-data-msg">데이터 없음</div></div>'
            continue

        def delta(key):
            cv = d.get(key)
            pv = prev_day.get(nick, {}).get(key)
            if cv is None or pv is None: return ''
            diff = int(cv) - int(pv)
            if diff == 0: return ''
            cls = 'up' if diff > 0 else 'down'
            sign = '+' if diff > 0 else ''
            return f'<span class="delta {cls}">{sign}{fmt_num(diff)}</span>'

        lv_delta = ''
        plv = prev_day.get(nick, {}).get('level')
        clv = d.get('level')
        if plv and clv and int(clv) > int(plv):
            lv_delta = f'<span class="delta up">+{int(clv)-int(plv)}</span>'

        collected_kst = datetime.fromisoformat(d['collected_at']).astimezone(KST).strftime('%H:%M')

        cards += f'''<div class="card">
            <div class="card-title">🍁 {nick}</div>
            <div class="stat-row"><span class="lbl">레벨</span>
                <span class="val">Lv.{d.get("level") or "-"} {lv_delta}</span>
                <span class="exp">({d.get("exp_pct") or "-"}%)</span></div>
            <div class="stat-row"><span class="lbl">전투력</span>
                <span class="val hl">{fmt_num(d.get("combat_power"))}</span>
                {delta("combat_power")}</div>
            <div class="stat-row"><span class="lbl">환산(380)</span>
                <span class="val or">{d.get("stat_equiv_380") or "-"}</span>
                {delta("stat_equiv_380")}</div>
            <div class="stat-row"><span class="lbl">헥사환산(380)</span>
                <span class="val pu">{d.get("hexa_equiv_380") or "-"}</span>
                {delta("hexa_equiv_380")}</div>
            <div class="fetched">🕐 {collected_kst} KST</div>
        </div>'''

    show = '' if di == 0 else 'style="display:none"'
    tab_contents += f'<div class="tab-content" id="tab-{date}" {show}><div class="cards">{cards}</div></div>'

table_rows = ''
for r in reversed(rows):
    dt = datetime.fromisoformat(r['collected_at']).astimezone(KST).strftime('%Y-%m-%d %H:%M')
    table_rows += f'''<tr>
        <td>{dt}</td>
        <td class="nick">{r["nick"]}</td>
        <td>Lv.{r.get("level") or "-"} ({r.get("exp_pct") or "-"}%)</td>
        <td class="hl">{fmt_num(r.get("combat_power"))}</td>
        <td class="or">{r.get("stat_equiv_380") or "-"}</td>
        <td class="pu">{r.get("hexa_equiv_380") or "-"}</td>
    </tr>'''

charts_html = ''
colors = ['#ff6b2b','#4a9eff','#2ecc71','#a78bfa','#ffb347','#e74c3c']
for i, nick in enumerate(all_nicks):
    c = colors[i % len(colors)]
    charts_html += f'<div class="chart-wrap"><div class="chart-title" style="color:{c}">🍁 {nick}</div><canvas id="chart-{i}"></canvas></div>'

level_charts_html = ''
for i, nick in enumerate(all_nicks):
    c = colors[i % len(colors)]
    level_charts_html += f'<div class="chart-wrap"><div class="chart-title" style="color:{c}">🍁 {nick}</div><canvas id="lchart-{i}"></canvas></div>'

chart_js = 'const chartData = ' + json.dumps(chart_data, ensure_ascii=False) + ';\n'
chart_js += 'const allNicks = ' + json.dumps(all_nicks, ensure_ascii=False) + ';\n'
chart_js += f'const colors = {json.dumps(colors)};\n'
chart_js += '''
const chartInstances = [];

allNicks.forEach((nick, i) => {
    const d = chartData[nick];

    const ctx1 = document.getElementById("chart-"+i);
    if (ctx1) {
        const c1 = new Chart(ctx1, {
            type: 'line',
            data: {
                labels: d.labels,
                datasets: [{
                    label: '환산(380)',
                    data: d.stat_equiv_380,
                    borderColor: colors[i % colors.length],
                    backgroundColor: colors[i % colors.length] + '22',
                    tension: 0.3, fill: true, pointRadius: 4,
                }, {
                    label: '헥사환산(380)',
                    data: d.hexa_equiv_380,
                    borderColor: '#a78bfa',
                    backgroundColor: '#a78bfa22',
                    tension: 0.3, fill: false, pointRadius: 4,
                    borderDash: [4,4],
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: { legend: { labels: { color: '#8892a4' } } },
                scales: {
                    x: { ticks: { color: '#8892a4', maxTicksLimit: 10 }, grid: { color: '#252a3a' } },
                    y: { ticks: { color: '#8892a4' }, grid: { color: '#252a3a' } }
                }
            }
        });
        chartInstances.push(c1);
    }

    const ctx2 = document.getElementById("lchart-"+i);
    if (ctx2) {
        const c2 = new Chart(ctx2, {
            type: 'line',
            data: {
                labels: d.labels,
                datasets: [{
                    label: '경험치%',
                    data: d.exp_pct,
                    borderColor: colors[i % colors.length],
                    backgroundColor: colors[i % colors.length] + '22',
                    tension: 0.3, fill: true, pointRadius: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { labels: { color: '#8892a4' } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const lv = d.level[ctx.dataIndex];
                                return `Lv.${lv} (${ctx.raw}%)`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: '#8892a4',
                            maxTicksLimit: 10,
                            callback: function(val, idx) {
                                const lv = d.level[idx];
                                return [d.labels[idx], `Lv.${lv}`];
                            }
                        },
                        grid: { color: '#252a3a' }
                    },
                    y: {
                        ticks: { color: '#2ecc71', callback: (v) => v + '%' },
                        grid: { color: '#252a3a' },
                        title: { display: true, text: '경험치%', color: '#2ecc71' }
                    }
                }
            }
        });
        chartInstances.push(c2);
    }
});

function toggleChart(mode) {
    document.getElementById('chart-section').style.display = mode === 'stat' ? 'grid' : 'none';
    document.getElementById('level-section').style.display = mode === 'level' ? 'grid' : 'none';
    document.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-' + mode).classList.add('active');
    
    chartInstances.forEach(chart => chart.resize());
}
'''

updated = datetime.now(KST).strftime('%Y-%m-%d %H:%M')

# f-string 내부의 모든 CSS와 JS 중괄호({})를 더블 중괄호({{}})로 완벽 교정했습니다.
html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🍁 메이플 스펙 트래커</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&family=JetBrains+Mono:wght@400;600&display=swap');
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0d0f14;color:#e8eaf0;font-family:"Noto Sans KR",sans-serif;min-height:100vh}}
  header{{background:linear-gradient(135deg,#1a1025,#0d1520);border-bottom:1px solid #252a3a;padding:16px 24px;display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:100;backdrop-filter:blur(10px)}}
  header h1{{font-size:20px;font-weight:900;background:linear-gradient(90deg,#ff6b2b,#ffb347);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}}
  header .upd{{font-size:12px;color:#8892a4;margin-left:auto}}
  .container{{max-width:1200px;margin:0 auto;padding:24px}}
  .section-title{{font-size:12px;color:#8892a4;text-transform:uppercase;letter-spacing:1px;margin:28px 0 12px}}
  .tab-bar{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}}
  .tab-btn{{padding:6px 14px;border-radius:6px;border:1px solid #252a3a;background:#151820;color:#8892a4;cursor:pointer;font-size:12px;font-family:"Noto Sans KR",sans-serif}}
  .tab-btn.active{{background:#ff6b2b;border-color:#ff6b2b;color:#fff}}
  .cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}}
  .card{{background:#151820;border:1px solid #252a3a;border-radius:10px;padding:16px;transition:border-color .2s}}
  .card:hover{{border-color:#ff6b2b44}}
  .card.no-data{{opacity:.4}}
  .no-data-msg{{font-size:12px;color:#8892a4;margin-top:8px}}
  .card-title{{font-size:14px;font-weight:700;margin-bottom:12px}}
  .stat-row{{display:flex;align-items:center;gap:6px;padding:5px 0;border-bottom:1px solid #ffffff08;font-size:13px}}
  .lbl{{color:#8892a4;width:90px;flex-shrink:0;font-size:12px}}
  .val{{font-family:"JetBrains Mono",monospace;font-weight:600}}
  .hl{{color:#ffb347}}.or{{color:#ff6b2b}}.pu{{color:#a78bfa}}
  .exp{{font-size:11px;color:#8892a4}}
  .delta{{font-size:11px;padding:1px 6px;border-radius:10px;margin-left:4px}}
  .delta.up{{background:#2ecc7122;color:#2ecc71}}
  .delta.down{{background:#e74c3c22;color:#e74c3c}}
  .fetched{{font-size:11px;color:#555;margin-top:10px}}
  .toggle-bar{{display:flex;gap:0;margin-bottom:16px;background:#151820;border:1px solid #252a3a;border-radius:8px;overflow:hidden;width:fit-content}}
  .toggle-btn{{padding:8px 20px;border:none;background:transparent;color:#8892a4;cursor:pointer;font-size:13px;font-family:"Noto Sans KR",sans-serif;transition:all .15s}}
  .toggle-btn.active{{background:#ff6b2b;color:#fff}}
  .charts-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(500px,1fr));gap:20px}}
  .chart-wrap{{background:#151820;border:1px solid #252a3a;border-radius:10px;padding:16px;height:320px;position:relative}}
  .chart-title{{font-size:13px;font-weight:700;margin-bottom:12px}}
  table{{width:100%;border-collapse:collapse;font-size:12px}}
  th{{background:#1c2030;color:#8892a4;padding:8px 12px;text-align:left;font-size:11px;border-bottom:1px solid #252a3a;white-space:nowrap}}
  td{{padding:8px 12px;border-bottom:1px solid #ffffff05;font-family:"JetBrains Mono",monospace;white-space:nowrap}}
  td.nick{{font-family:"Noto Sans KR",sans-serif;color:#8892a4}}
  td.hl{{color:#ffb347}}td.or{{color:#ff6b2b}}td.pu{{color:#a78bfa}}
  tr:hover td{{background:#ffffff03}}
  .table-wrap{{overflow-x:auto}}
</style>
</head>
<body>
<header>
  <span style="font-size:22px">🍁</span>
  <h1>메이플 스펙 트래커</h1>
  <span class="upd">업데이트: {updated} KST</span>
</header>
<div class="container">
  <div class="section-title">📅 날짜별 현황</div>
  <div class="tab-bar">{tab_btns}</div>
  {tab_contents}

  <div class="section-title">📈 성장 그래프</div>
  <div class="toggle-bar">
    <button class="toggle-btn active" id="btn-stat" onclick="toggleChart('stat')">환산(380)</button>
    <button class="toggle-btn" id="btn-level" onclick="toggleChart('level')">레벨 / 경험치</button>
  </div>
  <div id="chart-section" class="charts-grid">{charts_html}</div>
  <div id="level-section" class="charts-grid" style="display:none">{level_charts_html}</div>

  <div class="section-title">📋 전체 기록</div>
  <div class="table-wrap">
  <table>
    <thead><tr><th>수집시각 (KST)</th><th>닉네임</th><th>레벨</th><th>전투력</th><th>환산(380)</th><th>헥사환산(380)</th></tr></thead>
    <tbody>{table_rows}</tbody>
  </table>
  </div>
</div>
<script>
function showTab(date){{
  document.querySelectorAll(".tab-content").forEach(el=>el.style.display="none");
  document.querySelectorAll(".tab-btn").forEach(el=>el.classList.remove("active"));
  document.getElementById("tab-"+date).style.display="block";
  document.getElementById("btn-"+date).classList.add("active");
}}
{chart_js}
</script>
</body>
</html>'''

os.makedirs('dashboard', exist_ok=True)
with open('dashboard/index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f'✅ 대시보드 빌드 완료: dashboard/index.html ({len(rows)}개 레코드)')
