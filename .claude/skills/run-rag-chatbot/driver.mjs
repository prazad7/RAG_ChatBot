#!/usr/bin/env node
// Headless-browser smoke driver for the Hybrid RAG Chatbot.
// Launches backend + frontend if not already running, then drives the real UI with
// Playwright: login -> upload a sample doc -> ask a question -> screenshot -> check
// console errors. Run from anywhere: `node .claude/skills/run-rag-chatbot/driver.mjs`.

import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { setTimeout as sleep } from "node:timers/promises";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const BACKEND_DIR = path.join(REPO_ROOT, "backend");
const FRONTEND_DIR = path.join(REPO_ROOT, "frontend");
const VENV_PYTHON = path.join(REPO_ROOT, ".venv", "Scripts", "python.exe");

const BACKEND_URL = "http://127.0.0.1:8600";
const FRONTEND_URL = "http://127.0.0.1:5190";
const SCREENSHOT_DIR = path.join(__dirname, "screenshots");

const USERNAME = process.env.RAG_APP_USERNAME || "admin";
const PASSWORD = process.env.RAG_APP_PASSWORD || "password@123";

function log(msg) {
  console.log(`[driver] ${msg}`);
}

async function waitForUrl(url, timeoutMs = 45000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok || res.status < 500) return true;
    } catch {
      // not up yet
    }
    await sleep(1000);
  }
  return false;
}

async function ensureBackend() {
  if (await waitForUrl(`${BACKEND_URL}/api/health`, 2000)) {
    log("Backend already running.");
    return null;
  }
  log("Starting backend (uvicorn)...");
  const proc = spawn(
    VENV_PYTHON,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8600"],
    { cwd: BACKEND_DIR, stdio: "ignore", detached: true }
  );
  proc.unref();
  const up = await waitForUrl(`${BACKEND_URL}/api/health`, 60000);
  if (!up) throw new Error("Backend did not become healthy within 60s. Check backend/.env is populated.");
  log("Backend is up.");
  return proc;
}

async function ensureFrontend() {
  if (await waitForUrl(FRONTEND_URL, 2000)) {
    log("Frontend already running.");
    return null;
  }
  log("Starting frontend (vite dev server)...");
  const npmCmd = process.platform === "win32" ? "npm.cmd" : "npm";
  const proc = spawn(npmCmd, ["run", "dev"], { cwd: FRONTEND_DIR, stdio: "ignore", detached: true });
  proc.unref();
  const up = await waitForUrl(FRONTEND_URL, 45000);
  if (!up) throw new Error("Frontend did not come up within 45s.");
  log("Frontend is up.");
  return proc;
}

async function main() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  await ensureBackend();
  await ensureFrontend();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  const page = await browser.newPage({ viewport: { width: 1400, height: 850 } });

  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  try {
    log(`Navigating to ${FRONTEND_URL}`);
    await page.goto(FRONTEND_URL, { waitUntil: "networkidle" });

    // Fresh localStorage token from a previous run could bounce us straight past
    // the login form (the app treats "token present" as authenticated) - always
    // start from a clean slate so this driver behaves the same on every run.
    await page.evaluate(() => localStorage.clear());
    await page.reload({ waitUntil: "networkidle" });

    log("Logging in...");
    await page.getByLabel("Username").fill(USERNAME);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.getByText("Retrieval configuration", { exact: false }).waitFor({ timeout: 10000 });

    log("Uploading a sample document...");
    const sampleFile = path.join(__dirname, "sample_docs", "sample_report.txt");
    await page.locator('input[type="file"]').setInputFiles(sampleFile);
    await page.getByText(/file\(s\) ingested/).waitFor({ timeout: 30000 });

    log("Asking a question...");
    await page.getByPlaceholder("Ask a question about your uploaded documents...").fill(
      "What was the Q3 net profit mentioned in the document?"
    );
    await page.getByRole("button", { name: "Send" }).click();

    log("Waiting for a grounded/ungrounded answer badge...");
    await page.locator(".grounded-badge").first().waitFor({ timeout: 60000 });

    const answerText = await page.locator(".chat-bubble.assistant .chat-content").first().innerText();
    log(`Assistant answered: ${answerText}`);

    const screenshotPath = path.join(SCREENSHOT_DIR, "smoke.png");
    await page.screenshot({ path: screenshotPath, fullPage: true });
    log(`Screenshot saved to ${screenshotPath}`);

    const relevantErrors = consoleErrors.filter((e) => !/DevTools|Autofill/.test(e));
    if (relevantErrors.length) {
      log("Console errors detected:");
      relevantErrors.forEach((e) => log(`  ${e}`));
      process.exitCode = 1;
    } else {
      log("No console errors. Smoke test PASSED.");
    }
  } catch (err) {
    const failurePath = path.join(SCREENSHOT_DIR, "failure.png");
    await page.screenshot({ path: failurePath, fullPage: true }).catch(() => {});
    log(`FAILED: ${err.message}`);
    log(`Failure screenshot saved to ${failurePath}`);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main();
