import { useState } from "react";
import { sendChatMessage } from "../api/client";
import { useSession } from "../context/SessionContext";
import ChatInput from "../components/ChatInput";
import ChatMessages from "../components/ChatMessages";
import ConfigPanel from "../components/ConfigPanel";
import FileUploader from "../components/FileUploader";
import GraphVisualizer from "../components/GraphVisualizer";
import ProcessingTimer from "../components/ProcessingTimer";

export default function ChatPage() {
  const { logout, sessionId } = useSession();
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const [selectedTurnId, setSelectedTurnId] = useState(null);
  const [hasDocuments, setHasDocuments] = useState(false);

  async function handleSend(text) {
    const userTurn = { turn_id: `user-${Date.now()}`, role: "user", content: text };
    setMessages((prev) => [...prev, userTurn]);
    setSending(true);
    try {
      const response = await sendChatMessage(text);
      const assistantTurn = { role: "assistant", content: response.answer, ...response };
      setMessages((prev) => [...prev, assistantTurn]);
      setSelectedTurnId(assistantTurn.turn_id);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          turn_id: `error-${Date.now()}`,
          role: "assistant",
          content: err?.response?.data?.detail || "Something went wrong contacting the backend.",
          sources: [],
          graph_context: { nodes: [], edges: [] },
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  const selectedTurn = messages.find((m) => m.turn_id === selectedTurnId);

  return (
    <div className="chat-page">
      <aside className="left-panel">
        <div className="panel-header">
          <h1>Hybrid RAG Chatbot</h1>
          <button className="logout-btn" onClick={logout}>Log out</button>
        </div>
        <div className="session-id">Session: {sessionId?.slice(0, 8)}...</div>
        <FileUploader onUploaded={() => setHasDocuments(true)} />
        <ConfigPanel />
        <div className="left-chat-input">
          <h3>Ask a question</h3>
          <ChatInput onSend={handleSend} disabled={sending || !hasDocuments} />
          {!hasDocuments && <div className="hint-text">Upload a document first.</div>}
        </div>
      </aside>

      <main className="right-panel">
        <div className="right-panel-top">
          <h2>Conversation</h2>
          <ProcessingTimer active={sending} />
        </div>
        <div className="right-panel-body">
          <ChatMessages messages={messages} selectedTurnId={selectedTurnId} onSelectTurn={setSelectedTurnId} />
          <div className="graph-sidebar">
            <GraphVisualizer graphContext={selectedTurn?.graph_context} />
          </div>
        </div>
      </main>
    </div>
  );
}
