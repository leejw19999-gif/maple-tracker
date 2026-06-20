# 🍁 메이플 스펙 트래커

maplescouter.com에서 캐릭터 스펙을 매일 자동 수집하고 Supabase DB에 저장합니다.

## 세팅 방법

### 1. Supabase 테이블 생성
Supabase → SQL Editor에서 실행:
```sql
CREATE TABLE maple_records (
    id SERIAL PRIMARY KEY,
    collected_at TIMESTAMPTZ NOT NULL,
    nick TEXT NOT NULL,
    level INTEGER,
    exp_pct FLOAT,
    combat_power BIGINT,
    stat_equiv_380 INTEGER,
    hexa_equiv_380 INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_nick ON maple_records(nick);
CREATE INDEX idx_collected_at ON maple_records(collected_at);
```

### 2. GitHub Secrets 등록
레포 → Settings → Secrets and variables → Actions → New repository secret

| 이름 | 값 |
|------|-----|
| `SUPABASE_URL` | Supabase Project URL |
| `SUPABASE_KEY` | Supabase anon public key |
| `NICKNAMES` | `["닉네임1","닉네임2"]` (JSON 형식) |

### 3. GitHub Pages 활성화
레포 → Settings → Pages → Source: **gh-pages branch**

### 4. 수동 실행 테스트
Actions → 🍁 메이플 스펙 수집 → Run workflow

## 수집 스케줄
매일 오전 9시 KST (UTC 00:00) 자동 실행

## 대시보드
`https://{username}.github.io/{repo-name}/`
