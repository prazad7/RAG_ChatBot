import { useMemo, useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";

export default function GraphVisualizer({ graphContext }) {
  const containerRef = useRef(null);
  const hasData = graphContext?.nodes?.length > 0;

  const graphData = useMemo(() => {
    if (!hasData) return { nodes: [], links: [] };
    return {
      nodes: graphContext.nodes.map((n) => ({ id: n.id, label: n.labels?.[0] || "Entity" })),
      links: graphContext.edges.map((e) => ({ source: e.source, target: e.target, label: e.relation })),
    };
  }, [graphContext, hasData]);

  if (!hasData) {
    return <div className="graph-visualizer empty">No graph context for this answer.</div>;
  }

  return (
    <div className="graph-visualizer" ref={containerRef}>
      <h4>Graph context</h4>
      <div className="graph-canvas">
        <ForceGraph2D
          graphData={graphData}
          width={360}
          height={240}
          nodeLabel="id"
          linkLabel="label"
          nodeAutoColorBy="label"
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          nodeCanvasObject={(node, ctx, globalScale) => {
            const label = node.id;
            const fontSize = 10 / globalScale;
            ctx.font = `${fontSize}px sans-serif`;
            ctx.fillStyle = node.color || "#4c8bf5";
            ctx.beginPath();
            ctx.arc(node.x, node.y, 4, 0, 2 * Math.PI, false);
            ctx.fill();
            ctx.fillStyle = "var(--text-color, #222)";
            ctx.fillText(label, node.x + 6, node.y + 3);
          }}
        />
      </div>
    </div>
  );
}
