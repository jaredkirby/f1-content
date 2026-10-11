"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowUpRight, Check, Eye, EyeOff, KeyRound, LockKeyhole } from "lucide-react";
type Operation = { id: string; enabled: boolean; model: string; budgetUsd: number | null; maxCalls?: number; plannedCalls?: number; persistKeychain: boolean };
type Handoff = { id: string; status: "pending" | "consumed" | "expired"; expiresAt: number };

export default function KeyEntry({ operation }: { operation: Operation }) {
  const [key, setKey] = useState("");
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [handoff, setHandoff] = useState<Handoff | null>(null);
  const [error, setError] = useState("");
  const pending = useRef<{ id: string; key: string } | null>(null);
  useEffect(() => {
    fetch("/api/credential", { cache: "no-store" }).then(async (response) => {
      if (!response.ok) throw new Error("Sign in or reload to check the handoff.");
      const data = await response.json() as { item: Handoff | null; ready: boolean };
      setHandoff(data.item); setReady(data.ready);
    }).catch(() => setError("The handoff could not be checked. Please reload."));
  }, []);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    const value = key.trim();
    if (pending.current?.key !== value) pending.current = { key: value, id: crypto.randomUUID() };
    try {
      const response = await fetch("/api/credential", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: value, requestId: pending.current.id, operationId: operation.id, persistKeychain: operation.persistKeychain }) });
      const data = await response.json() as { item: Handoff; error?: string };
      if (!response.ok) throw new Error(data.error || "The key could not be sent.");
      setHandoff(data.item); setKey(""); setVisible(false); pending.current = null;
    } catch (e) { setError(e instanceof Error ? e.message : "The key could not be sent."); }
    finally { setBusy(false); }
  }
  const received = handoff?.status === "pending" || handoff?.status === "consumed";
  return <div className="site-shell key-shell">
    <header className="masthead"><a href="/" className="wordmark"><span className="mark">R<span>n</span></span>RACE NOTES</a><span className="private-tag"><span /> PRIVATE SETUP</span></header>
    <main className="key-main"><a href="/" className="back-link"><ArrowLeft size={15} /> Back to the video</a>
      <p className="eyebrow">OPENROUTER SETUP</p><h1>Your key.<br />Ready for the work.</h1>
      <p className="key-dek">{operation.persistKeychain ? "Save OpenRouter securely on your Mac, then run the quality checks. Future runs can use the saved key." : "Connect OpenRouter from your phone for this candidate."}</p>
      <div className="run-summary"><div><span>MODEL</span><strong>{operation.model}</strong></div><div><span>SPENDING CAP</span><strong>{operation.budgetUsd !== null ? `$${operation.budgetUsd.toFixed(2)}` : "Not authorized"}</strong></div><p>{operation.plannedCalls ?? 1} planned calls. Up to {operation.maxCalls ?? 1} per declared plan. Your feedback still decides quality.</p></div>
      {received ? <section className="handoff-success" role="status"><Check size={27} /><h2>{handoff.status === "pending" ? "Key received privately." : "Key collected for the run."}</h2><p>{handoff.status === "pending" ? "The encrypted handoff can be collected for 30 minutes. Return to our chat and say “ready” so I can continue." : "The temporary web handoff has been cleared. Return to our chat for local storage and run status."}</p><a href="/">Return to the video <ArrowUpRight size={15} /></a><button className="replace-key" onClick={() => { setHandoff(null); setKey(""); setVisible(false); pending.current = null; }}>Send a replacement key</button></section> : <form className="key-form" onSubmit={submit}>
        <label htmlFor="provider-key"><KeyRound size={16} /> OpenRouter API key</label>
        <div className="key-input"><input id="provider-key" type={visible ? "text" : "password"} autoComplete="off" autoCapitalize="none" spellCheck={false} maxLength={512} required value={key} onChange={(event) => setKey(event.target.value)} placeholder="Paste your key" /><button type="button" aria-label={visible ? "Hide key" : "Show key"} onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={18} /> : <Eye size={18} />}</button></div>
        <a className="create-key-link" href="https://openrouter.ai/settings/keys" target="_blank" rel="noreferrer">Create or manage an OpenRouter key <ArrowUpRight size={14} /></a>
        <button className="send-key" disabled={busy || !ready || !operation.enabled || !key.trim()}>{busy ? "Sending privately…" : operation.persistKeychain ? "Save on my Mac and run checks" : "Send key for this run"}<ArrowUpRight size={17} /></button>
        {!ready && !error && <p className="storage-note">Checking the private handoff…</p>}
        {handoff?.status === "expired" && <p className="storage-note">The previous handoff expired. You can send the key again.</p>}
      </form>}
      <p className="error-message" role="alert">{error}</p>
      <div className="key-privacy"><LockKeyhole size={18} /><div><h3>Keep the key out of chat.</h3><p>It travels over HTTPS to this private Site, is encrypted temporarily, and is collected once by the local pipeline. {operation.persistKeychain ? "The local pipeline saves it in this Mac’s login Keychain for later runs; storage must succeed before model calls. " : ""}It is never added to model prompts or feedback. Expired or collected web handoffs are cleared when accessed.</p></div></div>
    </main><footer><span>RACE NOTES</span><span>WATCH. NOTICE. SHAPE.</span></footer>
  </div>;
}
