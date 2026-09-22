export default function SourceAttributions({ sources }) {
  if (!sources?.length) return null;

  return (
    <div className="source-attributions">
      <h4>Sources</h4>
      <ul>
        {sources.map((s, i) => (
          <li key={i}>
            <div className="source-header">
              <span className="source-file">{s.file_name}</span>
              <span className="source-badge">{s.retriever}</span>
              <span className="source-score">{(s.score * 100).toFixed(1)}%</span>
            </div>
            <div className="source-preview">{s.preview}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}
