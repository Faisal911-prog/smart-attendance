import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";

// Camera-based QR scanner. Calls onResult(text) once and then stops the camera.
export default function QrScanner({ onResult }) {
  const regionId = "qr-reader";
  const scannerRef = useRef(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  async function stop() {
    const scanner = scannerRef.current;
    scannerRef.current = null;
    if (scanner) {
      try {
        await scanner.stop();
        scanner.clear();
      } catch {
        /* the scanner was not running */
      }
    }
    setRunning(false);
  }

  async function start() {
    setError("");
    try {
      const scanner = new Html5Qrcode(regionId);
      scannerRef.current = scanner;
      await scanner.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 240, height: 240 } },
        (text) => {
          stop();
          onResult(text);
        },
        () => {},
      );
      setRunning(true);
    } catch {
      scannerRef.current = null;
      setError(
        "The camera could not be opened. Allow camera access in the browser, or scan the QR code with your phone's camera app, or paste the code below.",
      );
    }
  }

  useEffect(() => {
    return () => {
      stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <div id={regionId} className="qr-region" />
      {error && <div className="alert alert-error">{error}</div>}
      {running ? (
        <button className="btn btn-secondary" onClick={stop}>
          Stop camera
        </button>
      ) : (
        <button className="btn" onClick={start}>
          Open camera and scan
        </button>
      )}
    </div>
  );
}
