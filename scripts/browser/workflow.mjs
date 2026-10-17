// Genuine local-model run and real browser controls. No model or API interception.
import { chromium } from "playwright";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const demo = process.argv.includes("--demo");
const base = "http://127.0.0.1:4173";
const output = path.join(root, "backend/validation");
const recordingDir = path.join(root, "backend/runtime/browser-recordings");
if (demo) await fs.mkdir(recordingDir, { recursive: true });
const reportPrefix = process.env.VALIDATION_PREFIX || "phase3";
await fs.mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || "/opt/google/chrome/chrome",
  headless: true, args: ["--no-sandbox", "--autoplay-policy=no-user-gesture-required"] });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 },
  ...(demo ? { recordVideo: { dir: recordingDir, size: { width: 1280, height: 900 } } } : {}) });
const page = await context.newPage();
page.setDefaultTimeout(15000);
const errors = [];
page.on("pageerror", e => errors.push(e.message));
const started = Date.now();
const report = { executed_at: new Date().toISOString(), kind: "real local model, real MCP, live weather, browser actions; synthetic households",
  scripted_review: true, agronomist_review: false, demo, checks: [], status: "failed" };
const check = text => { report.checks.push(text); console.log(text); };
const pause = async seconds => { if (demo) await new Promise(resolve => setTimeout(resolve, seconds * 1000)); };
async function login(phone) {
  await page.goto(base + "/auth-options");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.getByLabel("Phone Number", { exact: true }).fill(phone);
  await page.getByLabel("Password", { exact: true }).fill("SyntheticDemo123!");
  await page.getByRole("button", { name: "Sign In", exact: true }).last().click();
  await page.waitForURL("**/main-page");
}
try {
  await login("+251900000002");
  check("Officer logs in through the real form");
  await pause(1);
  await page.goto(base + "/workspace");
  const clusters = page.getByRole("combobox", { name: /^Household cluster/ });
  await clusters.selectOption({ label: process.env.DEMO_CLUSTER_LABEL || "SYNTHETIC cluster · Synthetic" });
  if (process.env.DEMO_TASK) await page.getByLabel("Requested task").fill(process.env.DEMO_TASK);
  await pause(1);
  const response = page.waitForResponse(r => r.url().endsWith("/runs") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Start advisory run", exact: true }).click();
  const created = await (await response).json();
  report.run_id = created.id;
  check("Cluster selection starts a persisted real agent run");
  const token = await page.evaluate(() => localStorage.getItem("agriroots_access_token"));
  const headers = { Authorization: `Bearer ${token}` };
  const api = "http://127.0.0.1:8000";
  const who = await (await context.request.get(api + "/api/workspace/me", { headers })).json();
  const prefix = api + "/api/workspace/offices/" + who.memberships[0].office_id;
  let run;
  const deadline = Date.now() + 240000;
  while (Date.now() < deadline) {
    run = await (await context.request.get(prefix + "/runs/" + created.id, { headers })).json();
    await page.getByRole("heading", { name: "Model and tool activity", exact: true }).evaluate(e => e.scrollIntoView({ block: "start" }));
    const details = page.locator("article[aria-live] details");
    await details.evaluateAll(nodes => nodes.forEach((e, i) => { e.open = i === nodes.length - 1; }));
    if (!["queued", "running"].includes(run.status)) break;
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
  report.run = run;
  assert.equal(run.status, "pending_review", JSON.stringify(run.error));
  assert.ok(run.calls.some(c => c.tool_name === "save_advisory_draft" && !c.error));
  assert.ok(run.calls.some(c => c.tool_name === "borrowed_mcp.fetch" && !c.error));
  check("Real open-weights run stops at pending review with visible tool activity");
  await pause(2);
  await page.getByRole("link", { name: "Open the saved draft in the review queue" }).click();
  let card = page.locator("#review-and-release article").filter({ hasText: run.advisory_id });
  await card.getByText("Evidence:", { exact: false }).first().click();
  assert.ok(await card.locator("details").count() >= 5);
  await page.screenshot({ path: path.join(output, demo ? "demo-evidence.png" : "browser-evidence.png") });
  check("Officer can inspect five stored evidence snapshots");
  await pause(4);
  if (!demo) {
    await card.getByLabel("Rejection / cancellation reason").fill("Synthetic browser check: field observations needed.");
    await card.getByRole("button", { name: "Reject", exact: true }).click();
    await card.getByRole("button", { name: "Submit for review", exact: true }).waitFor();
    check("Officer rejects a draft with an audited reason");
    await card.getByRole("button", { name: "Edit into new draft" }).click();
    await page.getByLabel("Title", { exact: true }).fill("SYNTHETIC corrected browser advisory");
    await page.getByRole("button", { name: "Save draft version", exact: true }).click();
    await card.getByRole("button", { name: "Submit for review", exact: true }).click();
    await card.getByRole("button", { name: "Approve exact version" }).waitFor();
    check("Correction creates version two requiring review");
  }
  await card.getByRole("button", { name: "Approve exact version" }).click();
  await card.getByRole("button", { name: "Release approved version to farmers" }).waitFor();
  const versions = await (await context.request.get(prefix + "/advisories", { headers })).json();
  const version = versions.find(v => v.advisory_id === run.advisory_id && v.status === "approved");
  assert.ok(version);
  check("Approval requires a separate explicit release action");
  await pause(3);
  await card.getByRole("button", { name: "Release approved version to farmers" }).click();
  await card.getByRole("heading").filter({ hasText: "released" }).waitFor();
  check("Officer explicitly releases the exact approved version");
  await pause(2);
  await login(process.env.DEMO_FARMER_PHONE || "+251900000003");
  const releasedResponse = page.waitForResponse(r => r.url() === api + "/api/workspace/released" && r.request().method() === "GET");
  await page.goto(base + "/advisories");
  const delivered = await (await releasedResponse).json();
  const receivedIndex = delivered.findIndex(v => v.id === version.id);
  assert.ok(receivedIndex >= 0, "The newly released exact version must reach this recipient");
  report.farmer_received_version_id = delivered[receivedIndex].id;
  const farmerCard = page.locator("article").nth(receivedIndex);
  await farmerCard.getByRole("heading").waitFor();
  assert.ok((await farmerCard.textContent()).includes(version.content.recommendations[0].action));
  await farmerCard.getByText("Supporting evidence", { exact: true }).first().click();
  check("Farmer sees the exact released action and supporting evidence");
  await pause(6);
  await farmerCard.getByRole("button", { name: "Listen to released advice" }).click();
  const audio = farmerCard.locator("audio");
  await audio.waitFor();
  await audio.evaluate(async element => { await element.play(); });
  await page.waitForFunction(() => [...document.querySelectorAll("audio")].some(a => a.currentTime > 0.25 && !a.paused && a.readyState >= 2));
  report.voice = "Real local eSpeak NG audio decoded and advanced during HTML audio playback; no cloud credentials or provider test double.";
  check("Farmer plays real locally synthesized released advice");
  await pause(3);
  if (!demo) {
    const forbidden = await context.request.get(prefix + "/runs/" + run.id, {
      headers: { Authorization: "Bearer " + await page.evaluate(() => localStorage.getItem("agriroots_access_token")) } });
    assert.equal(forbidden.status(), 403);
    check("Farmer cannot inspect private run logs");
  }
  await page.screenshot({ path: path.join(output, demo ? "demo-farmer.png" : "browser-farmer.png") });
  assert.deepEqual(errors, []);
  report.status = "passed";
} catch (e) {
  await page.screenshot({ path: path.join(output, demo ? "demo-failure.png" : "browser-failure.png") }).catch(() => {});
  report.error = e.stack;
  console.error(e);
  process.exitCode = 1;
} finally {
  report.elapsed_seconds = (Date.now() - started) / 1000;
  report.page_errors = errors;
  const video = page.video();
  await context.close();
  if (video) {
    await video.saveAs(path.join(recordingDir, "officer-to-farmer.webm"));
    await video.delete();
    report.video = "backend/runtime/browser-recordings/officer-to-farmer.webm";
    report.under_three_minutes = report.elapsed_seconds < 180;
    if (!report.under_three_minutes) {
      report.workflow_status = report.status;
      report.status = "failed";
      report.error = "Continuous demonstration exceeded the three-minute submission limit; retain the real timing and retry under measured conditions.";
      process.exitCode = 1;
    }
  }
  await browser.close();
  await fs.writeFile(path.join(output, `${reportPrefix}-${demo ? "demo" : "browser"}.json`), JSON.stringify(report, null, 2) + "\n");
}
