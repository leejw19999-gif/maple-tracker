import os, re, json, asyncio
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright
from supabase import create_client

KST = timezone(timedelta(hours=9))

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
NICKNAMES    = json.loads(os.environ['NICKNAMES'])  # ["닉1","닉2"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def parse_num(s):
    if not s: return None
    s = s.replace(',', '').replace(' ', '')
    total = 0
    m = re.search(r'(\d+)억', s)
    if m: total += int(m.group(1)) * 100000000
    m = re.search(r'(\d+)만', s)
    if m: total += int(m.group(1)) * 10000
    m = re.search(r'만\s*(\d+)$', s)
    if m: total += int(m.group(1))
    elif re.search(r'억[^만]*(\d{1,4})$', s):
        m2 = re.search(r'억[^만]*(\d{1,4})$', s)
        if m2: total += int(m2.group(1))
    return total if total > 0 else None

def parse_body(body, nick):
    lv    = re.search(r'레벨\nLv\.(\d+)\s*\(([0-9.]+)%\)', body)
    cp    = re.search(r'전투력\n([\d억만 ,]+)', body)
    se380 = re.search(r'환산 \(380\)\n([\d,]+)', body)
    he380 = re.search(r'헥사환산 \(380\)\n([\d,]+)', body)
    return {
        'nick':           nick,
        'level':          int(lv.group(1)) if lv else None,
        'exp_pct':        float(lv.group(2)) if lv else None,
        'combat_power':   parse_num(cp.group(1)) if cp else None,
        'stat_equiv_380': int(se380.group(1).replace(',','')) if se380 else None,
        'hexa_equiv_380': int(he380.group(1).replace(',','')) if he380 else None,
    }

async def scrape(context, nick, max_retry=3):
    for attempt in range(max_retry):
        page = await context.new_page()
        try:
            await page.goto(
                f'https://maplescouter.com/info?name={nick}',
                wait_until='domcontentloaded', timeout=60000
            )
            for _ in range(20):
                await page.wait_for_timeout(1000)
                body = await page.inner_text('body')
                if 'Lv.' in body and len(body) > 1000:
                    return parse_body(body, nick)

            body = await page.inner_text('body')
            if 'Lv.' in body:
                return parse_body(body, nick)

            # 데이터 없으면 재시도
            print(f'    ⚠️ {nick} 렌더링 실패 ({attempt+1}/{max_retry}), 재시도...')
        except Exception as e:
            print(f'    ⚠️ {nick} 오류 ({attempt+1}/{max_retry}): {e}')
        finally:
            await page.close()

        await asyncio.sleep(5)  # 재시도 전 5초 대기

    raise Exception(f'{max_retry}회 재시도 모두 실패')

def save_to_db(entry, collected_at):
    row = {
        'collected_at':   collected_at.isoformat(),
        'nick':           entry['nick'],
        'level':          entry.get('level'),
        'exp_pct':        entry.get('exp_pct'),
        'combat_power':   entry.get('combat_power'),
        'stat_equiv_380': entry.get('stat_equiv_380'),
        'hexa_equiv_380': entry.get('hexa_equiv_380'),
    }
    supabase.table('maple_records').insert(row).execute()
    return row

async def main():
    now = datetime.now(KST)
    print(f'[{now.strftime("%Y-%m-%d %H:%M")} KST] 수집 시작 / 대상: {NICKNAMES}')

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage',
                  '--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            locale='ko-KR',
            viewport={'width': 1280, 'height': 800},
            extra_http_headers={'Accept-Language': 'ko-KR,ko;q=0.9'}
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        for nick in NICKNAMES:
            print(f'  → {nick}')
            try:
                entry = await scrape(context, nick)
                row = save_to_db(entry, now)
                print(f'    ✅ Lv.{row["level"]} ({row["exp_pct"]}%) | '
                      f'전투력:{row["combat_power"]} | '
                      f'환산380:{row["stat_equiv_380"]} | '
                      f'헥사380:{row["hexa_equiv_380"]}')
            except Exception as e:
                print(f'    ❌ {e}')
            await asyncio.sleep(3)

        await browser.close()

    print('✅ 완료')

asyncio.run(main())
