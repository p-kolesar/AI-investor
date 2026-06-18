import { useState, useRef, useEffect } from "react";
import { postChat } from "../api.js";

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [agentLoading, setAgentLoading] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);

  const anyLoading = chatLoading || agentLoading;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, anyLoading]);

  async function submit(triggerAgent) {
    const text = input.trim();
    if (!text) return;
    if (triggerAgent ? agentLoading : chatLoading) return;

    const userMsg = { role: "user", content: text };
    const next = [...messages, userMsg];
    setMessages(next);
    setInput("");
    setError(null);

    const setThisLoading = triggerAgent ? setAgentLoading : setChatLoading;
    setThisLoading(true);
    try {
      const { answer } = await postChat(next, triggerAgent);
      setMessages(prev => [...prev, { role: "assistant", content: answer }]);
    } catch (e) {
      setError(e.message);
    } finally {
      setThisLoading(false);
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
        {chatLoading && (
          <div className="chat-bubble assistant">
            <div className="chat-role">AI</div>
            <div className="chat-text chat-thinking">Thinking…</div>
          </div>
        )}
        {agentLoading && (
          <div className="chat-bubble assistant">
            <div className="chat-role">AI</div>
            <div className="chat-text chat-thinking">Running agent — this takes ~30s…</div>
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
          disabled={chatLoading}
        />
        <div className="chat-buttons">
          <button className="chat-send" onClick={() => submit(false)} disabled={chatLoading || !hasInput}>
            Send
          </button>
          <button className="chat-run" onClick={() => submit(true)} disabled={anyLoading || !hasInput}>
            Run Agent
          </button>
        </div>
      </div>
    </div>
  );
}
