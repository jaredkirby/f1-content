"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUpRight, Check, Copy, Maximize, MessageSquare, Pause, Play, Plus, Volume2, VolumeX, X } from "lucide-react";
import pilot from "./data/pilot.json";

type Entry = { id: string; kind: "annotation" | "decision"; outcome: "approved" | "rejected" | null; comment: string; timeSec: number | null; createdAt: string };
const stamp = (time: number) => `${Math.floor(time / 60)}:${Math.floor(time % 60).toString().padStart(2, "0")}`;

export default function Review() {
  const video = useRef<HTMLVideoElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const pending = useRef<{ payload: string; id: string } | null>(null);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [time, setTime] = useState(0);
  const [noteTime, setNoteTime] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [decisionComment, setDecisionComment] = useState("");
  const [choice, setChoice] = useState<"approved" | "rejected">("approved");
  const [items, setItems] = useState<Entry[]>([]);
  const [decision, setDecision] = useState<Entry | null>(null);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [mediaError, setMediaError] = useState(false);

  async function loadFeedback() {
    const response = await fetch("/api/feedback", { cache: "no-store" });
    if (!response.ok) throw new Error("Saved feedback could not be loaded. Please reload or use this chat.");
    const data = await response.json() as { items: Entry[]; decision: Entry | null };
    setItems(data.items); setDecision(data.decision); setReady(true);
  }
  useEffect(() => { loadFeedback().catch((e) => setError(e.message)); }, []);
  async function toggle() {
    if (!video.current) return;
    if (video.current.paused) {
      try { await video.current.play(); } catch { setError("Playback could not start. Tap play again."); }
    } else video.current.pause();
  }
  function seek(value: number) { if (video.current) video.current.currentTime = value; setTime(value); }
  function annotate() {
    video.current?.pause();
    setNoteTime(Math.round((video.current?.currentTime ?? time) * 10) / 10);
    setMessage(""); composer.current?.focus(); composer.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  async function save(kind: "annotation" | "decision") {
    setBusy(true); setError(""); setMessage("");
    const values = { kind, outcome: kind === "decision" ? choice : null, comment: kind === "decision" ? decisionComment : comment,
      timeSec: kind === "decision" ? null : noteTime, manifestSha256: pilot.manifestSha256, videoSha256: pilot.videoSha256 };
    const payload = JSON.stringify(values);
    if (pending.current?.payload !== payload) pending.current = { payload, id: crypto.randomUUID() };
    try {
      const response = await fetch("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...values, requestId: pending.current.id }) });
      const data = await response.json() as { item: Entry; error?: string };
      if (!response.ok) throw new Error(data.error || "Your feedback could not be saved. Try again.");
      pending.current = null;
      setItems((previous) => [data.item, ...previous.filter((item) => item.id !== data.item.id)]);
      if (kind === "decision") { setDecision(data.item); setDecisionComment(""); dialog.current?.close(); }
      else { setComment(""); setNoteTime(null); }
      setMessage(kind === "decision" ? "Decision saved for this video." : "Note saved for this video.");
    } catch (e) { setError(e instanceof Error ? e.message : "Your feedback could not be saved."); }
    finally { setBusy(false); }
  }
  async function copyForChat() {
    const note = comment || decisionComment || "My feedback: ";
    const text = `Race Notes · ${pilot.eventLabel}\nVideo version ${pilot.version}${noteTime !== null ? ` · ${stamp(noteTime)}` : ""}\n${note}\n${window.location.origin}`;
    try { await navigator.clipboard.writeText(text); setMessage("Copied. Paste it into our existing chat."); }
    catch { setError("Copy is unavailable here. Tell me the moment and your feedback in our chat."); }
  }
  function decide(outcome: "approved" | "rejected") {
    video.current?.pause(); setChoice(outcome); setDecisionComment(""); setError(""); dialog.current?.showModal();
  }
  return <div className="site-shell">
    <header className="masthead"><a href="/" className="wordmark" aria-label="Race Notes home"><span className="mark">R<span>n</span></span>RACE NOTES</a><span className="private-tag"><span /> PRIVATE REVIEW</span></header>
    <main>
      <div className="intro"><p className="eyebrow">THE PHONE PILOT <span>{pilot.reviewLabel}</span></p><h1>{pilot.title}</h1><p className="dek">One story. Your feedback shapes the next edit.</p><p className="event-line">{pilot.eventLabel}<span>·</span>{Math.round(pilot.duration)} sec<span>·</span>9:16</p></div>
      <div className="review-grid">
        <section className="watch" aria-label="Watch the pilot">
          <div className="video-frame"><video ref={video} src={pilot.videoUrl} poster={pilot.posterUrl} playsInline preload="metadata" muted={muted}
            onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} onError={() => setMediaError(true)} aria-label={pilot.title} />
            {!playing && !mediaError && <button className="big-play" aria-label={time > 0 ? "Resume video" : "Play video"} onClick={toggle}><Play size={28} fill="currentColor" /></button>}
            {mediaError && <div className="media-error">The video could not load.<button onClick={() => { setMediaError(false); video.current?.load(); }}>Retry video</button></div>}
          </div>
          <div className="player-controls"><button onClick={toggle} aria-label={playing ? "Pause video" : "Play video"}>{playing ? <Pause size={19} /> : <Play size={19} />}</button><span className="timecode">{stamp(time)}</span><input aria-label="Video position" type="range" min="0" max={pilot.duration} step="0.1" value={time} onChange={(e) => seek(Number(e.target.value))} /><span className="timecode">{stamp(pilot.duration)}</span><button onClick={() => setMuted(!muted)} aria-label={muted ? "Unmute video" : "Mute video"}>{muted ? <VolumeX size={19} /> : <Volume2 size={19} />}</button><button className="fullscreen" aria-label="Full screen" onClick={() => video.current?.requestFullscreen().catch(() => setError("Full screen is unavailable in this browser."))}><Maximize size={18} /></button></div>
          <button className="moment-button" onClick={annotate}><Plus size={18} /> Add a note at this moment <span>{stamp(time)}</span></button>
          <p className="watch-hint">Watch with sound. Captions are part of the edit.</p>
        </section>
        <aside className="review-rail" aria-label="Your review">
          <div className="rail-heading"><span className="section-number">01</span><div><h2>Your eye, your call.</h2><p>One output. Tell me what earns its place.</p></div></div>
          <div className="review-status"><span className={`status-dot ${decision?.outcome || ""}`} /><span>{decision?.outcome === "approved" ? "Approved by you" : decision?.outcome === "rejected" ? "Changes requested" : "Awaiting your review"}</span></div>
          <div className="prompts"><p>Does the story feel grounded and clear?</p><p>Does the pace, voice and text work on your phone?</p></div>
          <form className="note-form" onSubmit={(e) => { e.preventDefault(); save("annotation"); }}>
            <div className="note-label"><label htmlFor="note">Leave a note</label>{noteTime !== null ? <button type="button" className="time-chip" onClick={() => setNoteTime(null)} aria-label="Remove timestamp">{stamp(noteTime)} <X size={12} /></button> : <span>Whole video</span>}</div>
            <textarea ref={composer} id="note" maxLength={4000} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="What works? What would you change?" rows={4} />
            <button type="submit" className="save-note" disabled={busy || !ready || !comment.trim()}><MessageSquare size={16} />{busy ? "Saving…" : "Save note"}<ArrowUpRight size={16} /></button>
          </form>
          <div className="chat-option"><Copy size={18} /><div><h3>Prefer our chat?</h3><p>Reply there with a moment and your feedback. Both paths count.</p><button onClick={copyForChat}>Copy note for chat <ArrowUpRight size={13} /></button></div></div>
          <p className="storage-note">Notes are private and saved to this video version. Only feedback you submit is recorded.</p>
          <div className="save-message" role="status" aria-live="polite">{message}</div><div className="error-message" role="alert">{error}</div>
          <div className="decision-bar"><button className="reject" onClick={() => decide("rejected")} disabled={busy || !ready}><X size={17} /> Reject</button><button className="approve" onClick={() => decide("approved")} disabled={busy || !ready}><Check size={17} /> Approve</button></div>
        </aside>
      </div>
      <section className="notes-section" aria-label="Saved feedback"><div className="notes-heading"><div><p className="eyebrow">THE REVIEW LOG</p><h2>Notes that shape the next edit.</h2></div><span>{items.length.toString().padStart(2, "0")} SAVED</span></div>
        {!ready ? <p className="empty-note">Loading your feedback…</p> : items.length === 0 ? <p className="empty-note"><ArrowDown size={18} /> Your first note starts the conversation.</p> : <ol className="notes-list">{items.map((item) => <li key={item.id}><div className="entry-label">{item.timeSec !== null ? <button onClick={() => { seek(item.timeSec!); video.current?.scrollIntoView({ behavior: "smooth", block: "center" }); }}>{stamp(item.timeSec)} <Play size={12} /></button> : <span>{item.kind === "decision" ? item.outcome === "approved" ? "APPROVED" : "REJECTED" : "WHOLE VIDEO"}</span>}<time dateTime={item.createdAt}>{new Date(item.createdAt).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</time></div><p>{item.comment || "Decision recorded."}</p></li>)}</ol>}
      </section>
      <details className="context"><summary>About this pilot <Plus size={15} /></summary><p>{pilot.authoringNote} Your feedback sets the quality bar for the next edit and future model choices.</p><p>{pilot.narration}</p><a href={pilot.scriptUrl} target="_blank" rel="noreferrer">Read the narration <ArrowUpRight size={14} /></a><p className="context-small">Private editorial review. Source footage credited to Formula 1. Footage reuse clearance has not been established.</p></details>
      {pilot.credentialHandoffEnabled && <a className="setup-link" href="/connect">Add the OpenRouter key from your phone <ArrowUpRight size={14} /></a>}
    </main>
    <footer><span>RACE NOTES</span><span>WATCH. NOTICE. SHAPE.</span></footer>
    <dialog ref={dialog} className="decision-dialog" onCancel={(event) => { if (busy) event.preventDefault(); }}><form onSubmit={(e) => { e.preventDefault(); save("decision"); }}><div className="dialog-heading"><p className="eyebrow">YOUR DECISION</p><button type="button" aria-label="Close decision" disabled={busy} onClick={() => dialog.current?.close()}><X size={20} /></button></div><h2>{choice === "approved" ? "This edit works." : "This edit needs changes."}</h2><label htmlFor="decision-comment">Anything to carry into the next edit? <span>Optional</span></label><textarea id="decision-comment" maxLength={4000} rows={4} value={decisionComment} onChange={(e) => setDecisionComment(e.target.value)} placeholder={choice === "approved" ? "What should we keep?" : "What needs to change?"} /><p className="error-message" role="alert">{error}</p><button className="confirm-decision" disabled={busy}>{busy ? "Saving…" : choice === "approved" ? "Save approval" : "Save rejection"}<Check size={17} /></button><p className="storage-note">Saved privately for this version. You can revise your decision later.</p></form></dialog>
  </div>;
}
