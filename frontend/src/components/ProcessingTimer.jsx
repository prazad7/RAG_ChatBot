import { useEffect, useState } from "react";

export default function ProcessingTimer({ active }) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!active) {
      setSeconds(0);
      return undefined;
    }
    const start = Date.now();
    const interval = setInterval(() => {
      setSeconds(((Date.now() - start) / 1000).toFixed(1));
    }, 100);
    return () => clearInterval(interval);
  }, [active]);

  if (!active) return null;

  return (
    <div className="processing-timer">
      <span className="spinner" /> Processing... {seconds}s
    </div>
  );
}
