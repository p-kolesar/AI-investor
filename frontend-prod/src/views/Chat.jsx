import { useState, useRef, useEffect } from "react";
import { postChat } from "../api.js";

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState("Thinking…");
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function submit(triggerAgent) {
    const text = input.trim();
    if (!text || loading) return;
    const next = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setLoading(true);
    setLoadingLabel(triggerAgent ? "Running agent — this takes ~30s…" : "Thinking…");
    setError(null);
    try {
      const { answer } = await postChat(next, triggerAgent);
      setMessages([...next, { role: "assistant", content: answer }]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function onKey(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(false); }
  }

  const hasInput = input.trim().length > 0;

  return (
    <div className="chat-wrap">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            Ask about the portfolio, or write a trading directive and click <b>Run Agent</b>.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble ${m.role}`}>
            <div className="chat-role">{m.role === "user" ? "You" : "AI"}</div>
            <div className="chat-text">{m.content}</div>
          </div>
        ))}
        {loading && (
          <div className="chat-bubble assistant">
            <div className="chat-role">AI</div>
            <div className="chat-text chat-thinking">{loadingLabel}</div>
          </div>
        )}
        {error && <div className="chat-error">{error}</div>}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-row">
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder="Ask about the portfolio… or write a trading directive to run the agent"
          rows={2}
          disabled={loading}
        />
        <div className="chat-buttons">
          <button className="chat-send" onClick={() => submit(false)} disabled={loading || !hasInput}>
            Send
          </button>
          <button className="chat-run" onClick={() => submit(true)} disabled={loading || !hasInput}>
            Run Agent
          </button>
        </div>
      </div>
    </div>
  );
}
