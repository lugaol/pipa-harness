// pipa_harness — OpenCode → session bus bridge (@@PIPA_MANAGED@@).
//
// Auto-discovered from ~/.config/opencode/plugin/. Forwards OpenCode
// activity into the pipa NDJSON flight recorder via `pipa hook`:
//   session-start / session-end / pre-tool / post-tool / post-model / note
// The spend ledger (tokens/cost/model) is captured separately by the
// LiteLLM gateway callback; this plugin provides the timeline.
//
// Rendered by pipa.runtime.wire_opencode — @@PIPA_BIN@@ and
// @@PIPA_RUNTIME@@ are substituted at wire time.

const PIPA_BIN = "@@PIPA_BIN@@"
const RUNTIME = "@@PIPA_RUNTIME@@"

let currentSession = null

function emit() {
  const args = Array.from(arguments)
  try {
    const proc = Bun.spawn([PIPA_BIN, "hook", ...args], {
      cwd: process.cwd(),
      stdin: "ignore",
      stdout: "ignore",
      stderr: "ignore",
      env: { ...process.env, PIPA_RUNTIME: RUNTIME },
    })
    proc.exited.catch(() => {})
  } catch {
    // never let observability break the session
  }
}

export default async () => {
  return {
    event: async ({ event }) => {
      try {
        const type = event && event.type ? String(event.type) : ""
        if (!type.startsWith("session.")) return
        const info = event.properties || event.attributes || {}
        const sid = info.sessionID || info.id || null
        if (!sid) return
        if (!currentSession || currentSession !== sid) {
          currentSession = sid
          emit("session-start", `id:${sid}`)
        }
        if (type === "session.idle" || type === "session.deleted") {
          emit("session-end")
          currentSession = null
        }
      } catch {
        // ignore malformed bus events
      }
    },

    "tool.execute.before": async (input) => {
      try {
        const tool = input && input.tool ? String(input.tool) : "unknown"
        emit("pre-tool", tool)
      } catch {}
    },

    "tool.execute.after": async (input, output) => {
      try {
        const tool = input && input.tool ? String(input.tool) : "unknown"
        const title =
          output && output.title ? ` ${String(output.title).slice(0, 120)}`
          : ""
        emit("post-tool", `${tool}${title}`)
      } catch {}
    },

    "chat.params": async (input, output) => {
      try {
        const opts = (output && output.args) || {}
        const model = opts.model || {}
        const mid = model.modelID || model.id || null
        if (mid) emit("post-model", String(mid))
      } catch {}
    },
  }
}
