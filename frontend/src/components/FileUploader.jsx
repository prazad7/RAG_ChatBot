import { useRef, useState } from "react";
import { uploadFiles } from "../api/client";

const ACCEPTED = ".pdf,.docx,.csv,.xlsx,.xls,.json,.xml,.txt";

export default function FileUploader({ onUploaded }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleFiles(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    setUploading(true);
    setError(null);
    try {
      const result = await uploadFiles(files);
      setLastResult(result);
      onUploaded?.(result);
    } catch (err) {
      setError(err?.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="file-uploader">
      <h3>Upload documents</h3>
      <div
        className={`dropzone ${dragging ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED}
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />
        {uploading ? "Uploading..." : "Drag files here or click to browse"}
        <div className="dropzone-hint">PDF, DOCX, CSV, XLSX, JSON, XML, TXT</div>
      </div>
      {error && <div className="error-text">{error}</div>}
      {lastResult && (
        <div className="upload-summary">
          <div>{lastResult.files_ingested.length} file(s) ingested, {lastResult.chunks_created} chunks</div>
          {lastResult.ocr_images_processed > 0 && <div>{lastResult.ocr_images_processed} image(s) OCR'd</div>}
          {lastResult.graph_nodes_created > 0 && <div>{lastResult.graph_nodes_created} graph nodes created</div>}
          {lastResult.warnings.map((w, i) => (
            <div key={i} className="warning-text">{w}</div>
          ))}
        </div>
      )}
    </div>
  );
}
