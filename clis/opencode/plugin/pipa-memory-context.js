// pipa_harness — memory-context plugin (@@PIPA_MANAGED@@).
//
// Auto-loads a compact memory digest into every system prompt, so the model
// consults vault + memory.db + code graph without having to remember to
// recall first (progressive disclosure: small core memory always in
// context, full notes fetched on demand with `pipa recall`).
//
// The digest is computed by `pipa recall --digest "<user text>"` — local,
// fast, best-effort; cached per session + last user message so it is NOT
// recomputed on every model call. Never fails the session.
//
// Disable with MEMORY_CONTEXT_DISABLED=1 (e.g. token pressure on a tiny
// local model). Adapted from ia_harness memory-context.ts to pipa's
// Bun-style plugin format (see pipa-session-bus.js).
//
// Rendered by pipa.runtime wire step — @@PIPA_BIN@@ substituted at wire time.

const PIPA_BIN = "@@PIPA_BIN@@"

const cache = new Map()

function extractText(parts) {
  if (!parts) return ""
  return parts
    .filter((p) => p && p.type === "text" && !p.synthetic && !p.ignored)
    .map((p) => p.text ?? "")
    .join("\n")
    .trim()
}

function sanitizeQuery(text) {
  return String(text).replace(/\s+/g, " ").trim().slice(0, 500)
}

function digestCap() {
  if (process.env.MEMORY_CONTEXT_DISABLED === "1") return 0
  const model = (process.env.OPENCODE_MODEL ?? "").toLowerCase()
  if (process.env.MEMORY_CONTEXT_SMALL === "1") return 1200
  if (/(qwen|4b|:9b|mini|llama|ollama)/.test(model)) return 1200
  const explicit = Number(process.env.MEMORY_CONTEXT_MAX_CHARS ?? "")
  if (Number.isFinite(explicit) && explicit > 0) return Math.min(explicit, 8000)
  return 4000
}

async function computeDigest(text) {
  try {
    const proc = Bun.spawn([PIPA_BIN, "recall", "--digest", text], {
      cwd: process.cwd(),
      stdout: "pipe",
      stderr: "ignore",
      env: { ...process.env },
    })
    const out = await new Response(proc.stdout).text()
    await proc.exited
    const digest = String(out ?? "").trim()
    if (!digest || digest === "(memory context unavailable)") return ""
    const cap = digestCap()
    if (cap <= 0 || digest.length <= cap) return digest
    return digest.slice(0, cap) + "\n…(truncated; use pipa recall for details)"
  } catch {
    return ""
  }
}

export default async () => {
  return {
    "chat.message": async (input, output) => {
      try {
        const sessionID = input.sessionID
        if (!sessionID) return
        const text = sanitizeQuery(extractText(output.parts))
        if (!text) return
        const prev = cache.get(sessionID)
        cache.set(sessionID, {
          messageID: (output.message && output.message.id) || (prev && prev.messageID) || "",
          text,
          digest: (prev && prev.digest) || "",
          digestMessageID: (prev && prev.digestMessageID) || "",
        })
      } catch {
        // never let observability break the session
      }
    },

    "experimental.chat.system.transform": async (input, output) => {
      if (process.env.MEMORY_CONTEXT_DISABLED === "1") return
      const sessionID = input.sessionID
      if (!sessionID) return
      try {
        const entry = cache.get(sessionID)
        const text = (entry && entry.text) || ""
        if (!text) return
        if (entry.digest && entry.digestMessageID === entry.messageID) {
          output.system.push(entry.digest)
          return
        }
        const digest = await computeDigest(text)
        if (!digest) return
        cache.set(sessionID, {
          messageID: entry.messageID, text,
          digest, digestMessageID: entry.messageID,
        })
        output.system.push(digest)
      } catch {
        // Memory must never break a session - leave the prompt untouched.
      }
    },
  }
}
