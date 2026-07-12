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
const resultTitle = document.getElementById('result-title');
const resultImg = document.getElementById('result-img');
const downloadBtn = document.getElementById('download-btn');

let currentObjectUrl = null;

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

function showResult(url, name) {
  if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl);
  currentObjectUrl = url;
  resultImg.src = url;
  resultTitle.textContent = `${name} 인포그래픽 리포트`;
  downloadBtn.href = url;
  downloadBtn.download = `${name}_company_insight.png`;
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
      fetch(`${API_BASE_URL}/api/report/${encodeURIComponent(name)}`, { method: 'POST' }),
      runInterstitialAd(),
    ]);

    if (response.ok) {
      const blob = await response.blob();
      showResult(URL.createObjectURL(blob), name);
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
