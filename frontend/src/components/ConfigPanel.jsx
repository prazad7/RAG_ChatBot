import { useState } from "react";
import { updateConfig } from "../api/client";

export default function ConfigPanel() {
  const [config, setConfig] = useState({
    use_dense: true,
    use_sparse: true,
    use_graph: true,
    use_rerank: true,
    top_k: 6,
  });
  const [saving, setSaving] = useState(false);

  async function apply(next) {
    setConfig(next);
    setSaving(true);
    try {
      await updateConfig(next);
    } finally {
      setSaving(false);
    }
  }

  function toggle(key) {
    apply({ ...config, [key]: !config[key] });
  }

  return (
    <div className="config-panel">
      <h3>Retrieval configuration {saving && <span className="saving-dot">saving...</span>}</h3>
      <div className="config-toggles">
        <label>
          <input type="checkbox" checked={config.use_dense} onChange={() => toggle("use_dense")} />
          Dense (embeddings)
        </label>
        <label>
          <input type="checkbox" checked={config.use_sparse} onChange={() => toggle("use_sparse")} />
          Sparse (BM25)
        </label>
        <label>
          <input type="checkbox" checked={config.use_graph} onChange={() => toggle("use_graph")} />
          Graph (Neo4j)
        </label>
        <label>
          <input type="checkbox" checked={config.use_rerank} onChange={() => toggle("use_rerank")} />
          Cross-encoder re-rank
        </label>
      </div>
      <label className="top-k-slider">
        Top-K: {config.top_k}
        <input
          type="range"
          min={1}
          max={12}
          value={config.top_k}
          onChange={(e) => apply({ ...config, top_k: Number(e.target.value) })}
        />
      </label>
    </div>
  );
}
