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
                    label: '레벨',
                    data: d.level,
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
                                const exp = d.exp_pct[ctx.dataIndex];
                                return `레벨: ${ctx.raw} (${exp}%)`;
                            }
                        }
                    }
                },
                scales: {
                    x: { ticks: { color: '#8892a4', maxTicksLimit: 10 }, grid: { color: '#252a3a' } },
                    y: { ticks: { color: '#2ecc71' }, grid: { color: '#252a3a' } }
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

updated = datetime.now(
