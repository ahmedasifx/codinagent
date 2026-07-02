import express, { Request, Response } from "express";
import { Sandbox } from "railway";

const app = express();
app.use(express.json({ limit: "10mb" }));

const PORT = parseInt(process.env.PORT ?? "3000", 10);
const IDLE_TIMEOUT_MINUTES = parseInt(
  process.env.SANDBOX_IDLE_TIMEOUT_MINUTES ?? "30",
  10
);

// ── Types ─────────────────────────────────────────────────────────────────────

type ExecHandle = ReturnType<Sandbox["exec"]>;

interface Session {
  sandbox: Sandbox;
  servers: Map<number, ExecHandle>;
  cfTunnels: Map<number, ExecHandle>;
  cfInstalled: boolean;
  pyInstalled: boolean;
}

// ── Session manager ───────────────────────────────────────────────────────────

const sessions = new Map<string, Session>();

async function getOrCreate(sessionId: string): Promise<Session> {
  const existing = sessions.get(sessionId);
  if (existing) return existing;

  const sandbox = await Sandbox.create({
    idleTimeoutMinutes: IDLE_TIMEOUT_MINUTES,
  });

  const session: Session = {
    sandbox,
    servers: new Map(),
    cfTunnels: new Map(),
    cfInstalled: false,
    pyInstalled: false,
  };
  sessions.set(sessionId, session);

  // Bootstrap eagerly so the first exec/exec-python doesn't pay the install cost,
  // but don't fail session creation over it — ensurePython retries lazily.
  ensurePython(session).catch((err) =>
    console.error("python bootstrap failed (will retry on demand):", err)
  );

  return session;
}

async function destroySession(sessionId: string): Promise<void> {
  const session = sessions.get(sessionId);
  if (!session) return;
  sessions.delete(sessionId);

  for (const handle of session.cfTunnels.values()) {
    try { await handle.kill(); } catch {}
  }
  for (const handle of session.servers.values()) {
    try { await handle.kill(); } catch {}
  }
  try { await session.sandbox.destroy(); } catch {}
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

async function waitForPort(sandbox: Sandbox, port: number): Promise<boolean> {
  for (let i = 0; i < 10; i++) {
    await sleep(2000);
    try {
      const r = await sandbox.exec(
        `curl -s -o /dev/null -w '%{http_code}' http://localhost:${port}`,
        { timeoutSec: 5 }
      );
      const code = r.stdout.trim();
      if (code && code !== "000") return true;
    } catch {}
  }
  return false;
}

async function ensurePython(session: Session): Promise<void> {
  if (session.pyInstalled) return;

  const check = await session.sandbox.exec("command -v python3", {
    timeoutSec: 15,
  });
  if (check.exitCode !== 0) {
    // Debian base image ships without python. Also point `python`/`pip` at the
    // python3 variants and disable PEP 668 so plain `pip install` works in this
    // disposable environment.
    const r = await session.sandbox.exec(
      "apt-get update -qq && " +
        "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-pip python3-venv && " +
        "printf '[global]\\nbreak-system-packages = true\\n' > /etc/pip.conf && " +
        "ln -sf \"$(command -v python3)\" /usr/local/bin/python && " +
        "ln -sf \"$(command -v pip3)\" /usr/local/bin/pip",
      { timeoutSec: 240 }
    );
    if (r.exitCode !== 0) {
      throw new Error(`python bootstrap failed: ${r.stderr.slice(-500)}`);
    }
  } else {
    // Python already present — still make pip usable on externally-managed distros.
    await session.sandbox.exec(
      "test -f /etc/pip.conf || printf '[global]\\nbreak-system-packages = true\\n' > /etc/pip.conf",
      { timeoutSec: 15 }
    );
  }
  session.pyInstalled = true;
}

async function ensureCloudflared(session: Session): Promise<void> {
  if (session.cfInstalled) return;
  await session.sandbox.exec(
    "curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared",
    { timeoutSec: 90 }
  );
  session.cfInstalled = true;
}

async function getTunnelUrl(
  session: Session,
  port: number
): Promise<string> {
  // Kill any existing tunnel on this port
  const old = session.cfTunnels.get(port);
  if (old) { try { await old.kill(); } catch {} }

  const chunks: string[] = [];
  const handle = session.sandbox.exec(
    `cloudflared tunnel --url http://localhost:${port} --no-autoupdate`,
    {
      onStdout: (c: string) => chunks.push(c),
      onStderr: (c: string) => chunks.push(c),
    }
  );
  session.cfTunnels.set(port, handle);

  // Poll for the URL in output (appears within ~5-10s)
  for (let i = 0; i < 20; i++) {
    await sleep(1000);
    const text = chunks.join("");
    const match = text.match(/https:\/\/[a-z0-9-]+\.trycloudflare\.com/);
    if (match) return match[0];
  }
  return "";
}

// ── Routes ────────────────────────────────────────────────────────────────────

app.post("/exec", async (req: Request, res: Response) => {
  const { session_id = "default", command, cwd, timeout = 120 } = req.body as {
    session_id?: string;
    command: string;
    cwd?: string;
    timeout?: number;
  };
  try {
    const session = await getOrCreate(session_id);
    // Commands that need the python toolchain wait for the bootstrap; everything
    // else (npm, mkdir, curl…) runs immediately.
    if (/\b(python3?|pip3?)\b/.test(command)) {
      await ensurePython(session);
    }
    const result = await session.sandbox.exec(command, {
      cwd,
      timeoutSec: timeout,
    });
    res.json({
      stdout: result.stdout,
      stderr: result.stderr,
      exit_code: result.exitCode ?? 1,
    });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

app.post("/exec-python", async (req: Request, res: Response) => {
  const { session_id = "default", code } = req.body as {
    session_id?: string;
    code: string;
  };
  try {
    const session = await getOrCreate(session_id);
    await ensurePython(session);
    const { sandbox } = session;
    const scriptPath = `/tmp/script_${Date.now()}.py`;
    await sandbox.files.write(scriptPath, code);
    const result = await sandbox.exec(`python3 ${scriptPath}`, {
      timeoutSec: 120,
    });
    res.json({
      stdout: result.stdout,
      stderr: result.stderr,
      exit_code: result.exitCode ?? 1,
    });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

app.post("/start-server", async (req: Request, res: Response) => {
  const { session_id = "default", command, port, cwd } = req.body as {
    session_id?: string;
    command: string;
    port: number;
    cwd?: string;
  };
  try {
    const session = await getOrCreate(session_id);
    const { sandbox } = session;

    if (/\b(python3?|pip3?|uvicorn|gunicorn|flask|streamlit)\b/.test(command)) {
      await ensurePython(session);
    }

    // Kill existing server on this port
    const existing = session.servers.get(port);
    if (existing) {
      try { await existing.kill(); } catch {}
      session.servers.delete(port);
    }

    // Start server in background
    const logs: string[] = [];
    const handle = sandbox.exec(command, {
      cwd,
      onStdout: (c: string) => { logs.push(c); },
      onStderr: (c: string) => { logs.push(c); },
    });
    session.servers.set(port, handle);

    const ready = await waitForPort(sandbox, port);
    const logTail = logs.slice(-30).join("");

    if (!ready) {
      res.json({ ready: false, logs: logTail, preview_url: "" });
      return;
    }

    // Get public URL via Cloudflare tunnel
    let previewUrl = "";
    try {
      await ensureCloudflared(session);
      previewUrl = await getTunnelUrl(session, port);
    } catch (err) {
      console.error("Cloudflare tunnel failed:", err);
    }

    res.json({ ready: true, logs: logTail, preview_url: previewUrl });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

app.post("/stop-server", async (req: Request, res: Response) => {
  const { session_id = "default", port } = req.body as {
    session_id?: string;
    port: number;
  };
  try {
    const session = sessions.get(session_id);
    if (!session) { res.json({ stopped: false }); return; }

    const handle = session.servers.get(port);
    if (!handle) { res.json({ stopped: false }); return; }

    await handle.kill();
    session.servers.delete(port);

    const cfHandle = session.cfTunnels.get(port);
    if (cfHandle) {
      try { await cfHandle.kill(); } catch {}
      session.cfTunnels.delete(port);
    }

    res.json({ stopped: true });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

app.post("/files/write", async (req: Request, res: Response) => {
  const { session_id = "default", path, content } = req.body as {
    session_id?: string;
    path: string;
    content: string;
  };
  try {
    const { sandbox } = await getOrCreate(session_id);
    // Ensure parent directory exists
    const parent = path.substring(0, path.lastIndexOf("/"));
    if (parent) {
      await sandbox.exec(`mkdir -p "${parent}"`);
    }
    await sandbox.files.write(path, content);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

app.get("/files/read", async (req: Request, res: Response) => {
  const { session_id = "default", path } = req.query as {
    session_id?: string;
    path: string;
  };
  try {
    const { sandbox } = await getOrCreate(session_id);
    const content = await sandbox.files.read(path, { format: "text" });
    res.type("text/plain").send(content);
  } catch (err) {
    res.status(404).json({ error: String(err) });
  }
});

app.get("/files/list", async (req: Request, res: Response) => {
  const { session_id = "default", path = "." } = req.query as {
    session_id?: string;
    path?: string;
  };
  try {
    const { sandbox } = await getOrCreate(session_id);
    const entries = await sandbox.files.list(path);
    res.json(entries.map((e: { name: string; isDir: boolean }) => ({ name: e.name, is_dir: e.isDir })));
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

app.delete("/sandbox", async (req: Request, res: Response) => {
  const session_id = (req.query.session_id as string) ?? "default";
  await destroySession(session_id);
  res.json({ ok: true });
});

app.delete("/sandbox/all", async (_req: Request, res: Response) => {
  const ids = [...sessions.keys()];
  await Promise.allSettled(ids.map(destroySession));
  res.json({ ok: true });
});

app.get("/health", (_req: Request, res: Response) => {
  res.json({ status: "ok", sessions: sessions.size });
});

// ── Start ─────────────────────────────────────────────────────────────────────

app.listen(PORT, () => {
  console.log(`railway-bridge listening on :${PORT}`);
});
