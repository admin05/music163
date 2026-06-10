#!/usr/bin/env node
const { spawn } = require("child_process");
const https = require("https");
const path = require("path");

const projectRoot = __dirname;
const pythonScript = path.join(projectRoot, "arcadia_run.py");

function barkEndpoint(value) {
  if (/^https?:\/\//.test(value)) return value.replace(/\/$/, "");
  const server = (process.env.BARK_SERVER || "https://api.day.app").replace(/\/$/, "");
  return `${server}/${encodeURIComponent(value)}`;
}

function sendBark(title, body) {
  const bark = (process.env.BARK || "").trim();
  if (!bark) {
    console.log("[Bark] BARK 环境变量未配置，跳过启动失败推送。");
    return;
  }

  const payload = JSON.stringify({
    title,
    body,
    group: process.env.BARK_GROUP || "网易音乐人任务",
    level: "timeSensitive",
  });
  const url = new URL(barkEndpoint(bark));
  const req = https.request(
    {
      method: "POST",
      hostname: url.hostname,
      path: `${url.pathname}${url.search}`,
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(payload),
      },
    },
    (res) => {
      res.resume();
      res.on("end", () => console.log(`[Bark] 启动失败推送完成：HTTP ${res.statusCode}`));
    },
  );
  req.on("error", (err) => console.log(`[Bark] 启动失败推送异常：${err.message}`));
  req.write(payload);
  req.end();
}

function runWith(command) {
  return new Promise((resolve) => {
    const child = spawn(command, [pythonScript], {
      cwd: projectRoot,
      env: process.env,
      stdio: "inherit",
    });
    child.on("error", (err) => resolve({ command, error: err }));
    child.on("exit", (code, signal) => resolve({ command, code, signal }));
  });
}

(async () => {
  const candidates = [process.env.PYTHON, "python3", "python"].filter(Boolean);
  const tried = [];

  for (const command of candidates) {
    const result = await runWith(command);
    tried.push(command);
    if (!result.error) {
      if (result.signal) {
        process.exitCode = 1;
        return;
      }
      process.exitCode = result.code || 0;
      return;
    }
    if (result.error.code !== "ENOENT") {
      console.error(`[Arcadia] 启动 ${command} 失败：${result.error.message}`);
      sendBark("网易音乐人任务启动失败", `Python 启动失败：${result.error.message}`);
      process.exitCode = 1;
      return;
    }
  }

  const message = `未找到可用 Python。已尝试：${tried.join(", ")}`;
  console.error(`[Arcadia] ${message}`);
  sendBark("网易音乐人任务启动失败", message);
  process.exitCode = 1;
})();
