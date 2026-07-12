import './style.css';
import { loadFullScreenAd, showFullScreenAd } from '@apps-in-toss/web-framework';

// ── 설정 ─────────────────────────────────────────────────────────
// 백엔드(FastAPI) 배포 주소. 빌드 시 VITE_API_BASE_URL 환경변수로 지정.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

// 앱인토스 전면광고 그룹 ID
const AD_GROUP_ID = 'ait.v2.live.a557ea481b1d4248';

// ── DOM ──────────────────────────────────────────────────────────
const form = document.getElementById('search-form');
const input = document.getElementById('company-input');
const btn = document.getElementById('submit-btn');
const loading = document.getElementById('loading');
const errorBox = document.getElementById('error-box');
const errorMsg = document.getElementById('error-msg');
const resultSection = document.getElementById('result-section');
const reportEl = document.getElementById('report');

function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }

function setLoading(active) {
  btn.disabled = active;
  btn.textContent = active ? '분석 중…' : '리포트 생성';
}

function showError(msg) {
  errorMsg.textContent = msg || '알 수 없는 오류가 발생했습니다.';
  show(errorBox);
  hide(loading);
  hide(resultSection);
}

// ── 포맷 헬퍼 ─────────────────────────────────────────────────────
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]));

function fmtEok(v) {
  if (v == null) return 'N/A';
  if (Math.abs(v) >= 10000) return `${(v / 10000).toFixed(1)}조`;
  return `${Math.round(v).toLocaleString('ko-KR')}억`;
}

function fmtWon(v) {
  return v == null ? 'N/A' : `${v.toLocaleString('ko-KR')}원`;
}

const signClass = (v) => (v == null ? '' : v >= 0 ? 'up' : 'down');

// ── 리포트 HTML 렌더링 ────────────────────────────────────────────
function renderReport(data) {
  const si = data.stock_info;
  const parts = [];

  // 헤더
  parts.push(`
    <div class="rp-head">
      <h2>${esc(data.company_name)}${data.stock_code ? ` <span class="rp-code">[${esc(data.stock_code)}]</span>` : ''}</h2>
    </div>
  `);

  // 현재 주가
  if (si && si.current_price != null) {
    const chg = si.price_change;
    const chgHtml = chg != null
      ? `<span class="rp-change ${signClass(chg)}">${chg >= 0 ? '▲' : '▼'} ${Math.abs(chg).toFixed(2)}%</span>`
      : '';
    const meta = [
      si.market_cap ? `시총 ${esc(si.market_cap)}` : null,
      si.per != null ? `PER ${si.per.toFixed(1)}x` : null,
      si.pbr != null ? `PBR ${si.pbr.toFixed(1)}x` : null,
    ].filter(Boolean).join('  ·  ');
    parts.push(`
      <div class="rp-card">
        <div class="rp-label">현재 주가</div>
        <div class="rp-price ${signClass(chg)}">${fmtWon(si.current_price)} ${chgHtml}</div>
        ${meta ? `<div class="rp-meta">${meta}</div>` : ''}
      </div>
    `);
  }

  // 재무제표
  if (data.financials && data.financials.length) {
    const rows = [...data.financials]
      .sort((a, b) => a.year - b.year)
      .map((f) => `
        <tr>
          <td>${f.year}</td>
          <td>${fmtEok(f.revenue)}</td>
          <td class="${signClass(f.operating_income)}">${fmtEok(f.operating_income)}</td>
          <td class="${signClass(f.net_income)}">${fmtEok(f.net_income)}</td>
        </tr>
      `).join('');
    parts.push(`
      <div class="rp-card">
        <div class="rp-label">💰 재무제표 <small>(단위: 억원)</small></div>
        <table class="rp-table">
          <thead><tr><th>연도</th><th>매출액</th><th>영업이익</th><th>순이익</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `);
  }

  // 배당
  const dv = data.dividend;
  if (dv && (dv.dps != null || dv.payout_ratio != null || dv.dividend_yield != null)) {
    parts.push(`
      <div class="rp-card">
        <div class="rp-label">📈 배당 정보</div>
        <div class="rp-stats">
          <div class="rp-stat"><span>주당배당금</span><strong>${dv.dps != null ? fmtWon(dv.dps) : 'N/A'}</strong></div>
          <div class="rp-stat"><span>배당성향</span><strong>${dv.payout_ratio != null ? dv.payout_ratio.toFixed(1) + '%' : 'N/A'}</strong></div>
          <div class="rp-stat"><span>시가배당률</span><strong>${dv.dividend_yield != null ? dv.dividend_yield.toFixed(2) + '%' : 'N/A'}</strong></div>
        </div>
      </div>
    `);
  }

  // 증권가 전망
  const con = data.consensus;
  if (con && con.target_avg != null) {
    const range = con.target_high != null && con.target_low != null
      ? `<div class="rp-meta">최고 ${fmtWon(con.target_high)}  /  최저 ${fmtWon(con.target_low)}</div>`
      : '';
    const upside = si && si.current_price
      ? `<div class="rp-meta">현재가 대비 <strong class="${signClass(con.target_avg - si.current_price)}">${(((con.target_avg / si.current_price) - 1) * 100).toFixed(1)}%</strong></div>`
      : '';
    let opinions = '';
    if (con.buy_count != null || con.neutral_count != null || con.sell_count != null) {
      opinions = `
        <div class="rp-opinions">
          <span class="op buy">매수 ${con.buy_count ?? 0}</span>
          <span class="op neutral">중립 ${con.neutral_count ?? 0}</span>
          <span class="op sell">매도 ${con.sell_count ?? 0}</span>
        </div>`;
    }
    parts.push(`
      <div class="rp-card">
        <div class="rp-label">🔮 증권가 전망</div>
        <div class="rp-target">목표주가 평균 <strong>${fmtWon(con.target_avg)}</strong></div>
        ${range}${upside}${opinions}
      </div>
    `);
  }

  // 데이터가 주가 외에 하나도 없을 때 안내
  if (parts.length <= 2 && !(si && si.current_price != null)) {
    parts.push(`<div class="rp-card"><div class="rp-meta">수집된 데이터가 없습니다.</div></div>`);
  }

  parts.push(`
    <div class="rp-footer">
      데이터 출처: DART Open API, 네이버 금융 · 투자 판단의 책임은 본인에게 있습니다
    </div>
  `);

  reportEl.innerHTML = parts.join('');
  hide(loading);
  hide(errorBox);
  show(resultSection);
}

// ── 전면광고 ──────────────────────────────────────────────────────
// 리포트 생성 시작 시 광고를 로드→노출하고, 광고 종료(dismissed) 후
// 준비된 결과를 보여준다. 토스 앱 밖(일반 브라우저)이나 광고 실패 시에는
// 광고 없이 바로 결과를 보여준다 (앱 중단 금지).
function runInterstitialAd() {
  return new Promise((resolve) => {
    let settled = false;
    const done = () => {
      if (!settled) {
        settled = true;
        resolve();
      }
    };
    // 광고가 10초 안에 못 뜨면 결과 표시를 막지 않는다
    const timeout = setTimeout(done, 10000);

    try {
      loadFullScreenAd({
        options: { adGroupId: AD_GROUP_ID },
        onEvent: (event) => {
          if (event.type === 'loaded') {
            try {
              showFullScreenAd({
                options: { adGroupId: AD_GROUP_ID },
                onEvent: (showEvent) => {
                  if (showEvent.type === 'dismissed' || showEvent.type === 'failedToShow') {
                    clearTimeout(timeout);
                    done();
                  }
                },
                onError: () => {
                  clearTimeout(timeout);
                  done();
                },
              });
            } catch {
              clearTimeout(timeout);
              done();
            }
          }
        },
        onError: () => {
          clearTimeout(timeout);
          done();
        },
      });
    } catch {
      // 토스 앱 밖(일반 브라우저)에서는 SDK 브릿지가 없어 예외 발생 — 광고 생략
      clearTimeout(timeout);
      done();
    }
  });
}

// ── 리포트 생성 ───────────────────────────────────────────────────
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = input.value.trim();
  if (!name) return;

  hide(errorBox);
  hide(resultSection);
  show(loading);
  setLoading(true);

  try {
    // 리포트 요청과 전면광고를 동시에 진행 — 광고가 끝나면 결과 표시
    const [response] = await Promise.all([
      fetch(`${API_BASE_URL}/api/data/${encodeURIComponent(name)}`),
      runInterstitialAd(),
    ]);

    if (response.ok) {
      renderReport(await response.json());
    } else {
      let detail = '서버 오류가 발생했습니다.';
      try {
        const json = await response.json();
        detail = json.detail || json.error || detail;
      } catch {}
      showError(detail);
    }
  } catch {
    showError('네트워크 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
  } finally {
    setLoading(false);
  }
});
