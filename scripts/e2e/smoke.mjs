/**
 * Playwright E2E smoke test — 회원가입 → 로그인 → 채팅(멀티턴)
 * 실행: node scripts/e2e/smoke.mjs
 * 사전 조건: frontend:8000, chatbot_api:8006, chatbot_server, Redis, MySQL
 */
import { chromium } from "playwright";

const BASE = process.env.E2E_BASE_URL || "http://localhost:8000";
const ts = Date.now();
const loginId = `e2e_${ts}`;
const password = "TestPass123!";
const displayName = "E2E테스터";

function log(step, detail = "") {
  console.log(`[${step}]${detail ? " " + detail : ""}`);
}

async function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(`console: ${msg.text()}`);
  });

  try {
    // 1) 홈
    log("1/6", "홈 페이지");
    await page.goto(BASE, { waitUntil: "networkidle" });
    await assert(
      (await page.title()).includes("내 찐친 고비"),
      "홈 타이틀 확인 실패"
    );

    // 2) 회원가입
    log("2/6", `회원가입 login_id=${loginId}`);
    await page.goto(`${BASE}/signup`, { waitUntil: "networkidle" });
    await page.fill("#login_id", loginId);
    await page.fill("#email", `${loginId}@example.com`);
    await page.fill("#display_name", displayName);
    await page.fill("#password", password);
    await page.fill("#password_confirm", password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/login/, { timeout: 10000 });

    // 3) 로그인
    log("3/6", "로그인");
    await page.fill("#login_id", loginId);
    await page.fill("#password", password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/(chat-app|$)/, { timeout: 10000 });

    // 4) 채팅 페이지
    log("4/6", "채팅 페이지 진입");
    if (!page.url().includes("/chat-app")) {
      await page.goto(`${BASE}/chat-app`, { waitUntil: "networkidle" });
    }
    await page.waitForSelector("#message-to-send", { timeout: 10000 });

    // 5) 첫 메시지 — OpenAI 응답 대기 (최대 25초)
    log("5/6", "첫 메시지 전송");
    const msg1 = "안녕! E2E 테스트야. 짧게 인사만 해줘.";
    await page.fill("#message-to-send", msg1);
    await page.press("#message-to-send", "Enter");
    await page.waitForFunction(
      () => {
        const bubbles = document.querySelectorAll(".other-message");
        if (bubbles.length === 0) return false;
        const last = bubbles[bubbles.length - 1];
        if (last.querySelector(".loading-dots")) return false;
        const text = (last.textContent || "").trim();
        return text.length > 0 && !text.includes("서버랑 연결이 안 돼");
      },
      { timeout: 25000 }
    );
    const reply1 = await page.locator(".other-message").last().textContent();
    log("5/6", `봇 응답: ${(reply1 || "").trim().slice(0, 80)}...`);
    await assert((reply1 || "").trim().length > 0, "첫 응답이 비어 있음");

    // 6) 멀티턴 두 번째 메시지
    log("6/6", "멀티턴 두 번째 메시지");
    const msg2 = "방금 한 말 기억해? 한 단어로만 답해.";
    await page.fill("#message-to-send", msg2);
    await page.press("#message-to-send", "Enter");
    await page.waitForFunction(
      (prevCount) => {
        const bubbles = document.querySelectorAll(".other-message");
        if (bubbles.length <= prevCount) return false;
        const last = bubbles[bubbles.length - 1];
        if (last.querySelector(".loading-dots")) return false;
        return (last.textContent || "").trim().length > 0;
      },
      await page.locator(".other-message").count(),
      { timeout: 25000 }
    );
    const reply2 = await page.locator(".other-message").last().textContent();
    log("6/6", `봇 응답: ${(reply2 || "").trim().slice(0, 80)}`);

    await assert(errors.length === 0, `페이지 에러: ${errors.join("; ")}`);
    console.log("\n✅ E2E smoke test PASSED");
  } catch (err) {
    console.error("\n❌ E2E smoke test FAILED:", err.message);
    if (errors.length) console.error("페이지 에러:", errors);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main();
