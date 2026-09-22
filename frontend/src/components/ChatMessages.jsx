import { useEffect, useRef } from "react";
import SourceAttributions from "./SourceAttributions";

export default function ChatMessages({ messages, selectedTurnId, onSelectTurn }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-messages">
      {messages.length === 0 && (
        <div className="empty-state">Upload a document on the left, then ask a question here.</div>
      )}
      {messages.map((m) => (
        <div
          key={m.turn_id}
          className={`chat-bubble ${m.role} ${m.turn_id === selectedTurnId ? "selected" : ""}`}
          onClick={() => m.role === "assistant" && onSelectTurn?.(m.turn_id)}
        >
          <div className="chat-role">{m.role === "user" ? "You" : "Assistant"}</div>
          <div className="chat-content">{m.content}</div>
          {m.role === "assistant" && (
            <div className="chat-meta">
              {typeof m.elapsed_seconds === "number" && <span>{m.elapsed_seconds.toFixed(2)}s</span>}
              {m.guardrail && (
                <span className={`grounded-badge ${m.guardrail.output_grounded ? "grounded" : "ungrounded"}`}>
                  {m.guardrail.output_grounded ? "Grounded" : "Not grounded"} (
                  {(m.guardrail.grounding_score * 100).toFixed(0)}%)
                </span>
              )}
            </div>
          )}
          {m.role === "assistant" && <SourceAttributions sources={m.sources} />}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
