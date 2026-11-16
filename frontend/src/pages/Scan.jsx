import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, errorMessage } from "../api.js";
import QrScanner from "../components/QrScanner.jsx";
import { Alert, Card } from "../components/ui.jsx";

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";
const TOKEN_PATTERN = /^\d+\.\d+\.[0-9a-f]{24}$/;

// The QR code contains a link such as https://app/scan?token=...; a bare token is accepted as well.
function extractToken(text) {
  const value = (text || "").trim();
  if (TOKEN_PATTERN.test(value)) return value;
  try {
    const token = new URL(value).searchParams.get("token");
    if (token && TOKEN_PATTERN.test(token)) return token;
  } catch {
    /* not a URL */
  }
  return null;
}

function getPosition() {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject({ code: 0 });
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 20000,
      maximumAge: 0,
    });
  });
}

function geolocationMessage(err) {
  switch (err && err.code) {
    case 1:
      return "Location permission was denied. Allow location access for this site in your browser settings and try again.";
    case 2:
      return "Your position could not be determined. Move closer to a window and try again.";
    case 3:
      return "Finding your position took too long. Try again.";
    default:
      return "This browser cannot provide your location.";
  }
}

export default function Scan() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token");

  const [pasted, setPasted] = useState("");
  const [pasteError, setPasteError] = useState("");
  const [phase, setPhase] = useState("idle"); // idle | locating | sending | done | failed
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [demo, setDemo] = useState({ latitude: "47.5316", longitude: "21.6273", accuracy: "10" });

  function acceptText(text) {
    const found = extractToken(text);
    if (!found) {
      setPasteError("This does not look like an attendance QR code.");
      return;
    }
    setPasteError("");
    navigate(`/scan?token=${encodeURIComponent(found)}`, { replace: true });
  }

  async function checkIn() {
    setError("");
    setResult(null);
    try {
      let coords;
      if (DEMO_MODE) {
        coords = {
          latitude: parseFloat(demo.latitude),
          longitude: parseFloat(demo.longitude),
          accuracy: parseFloat(demo.accuracy),
        };
      } else {
        setPhase("locating");
        const position = await getPosition();
        coords = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
        };
      }
      setPhase("sending");
      const response = await api.post("/attendance/scan/", { token, ...coords });
      setResult(response);
      setPhase("done");
    } catch (err) {
      setError(err && err.status !== undefined ? errorMessage(err) : geolocationMessage(err));
      setPhase("failed");
    }
  }

  const busy = phase === "locating" || phase === "sending";

  if (phase === "done" && result) {
    return (
      <div className="narrow">
        <Card className="result-ok">
          <div className="result-icon" aria-hidden="true">
            ✓
          </div>
          <h1>You are checked in</h1>
          <p>
            <strong>{result.course_code}</strong> · {result.course_name}
            <br />
            {result.session}
          </p>
          <Link className="btn" to="/student">
            Back to my attendance
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="narrow">
      <h1>Check in</h1>

      {!window.isSecureContext && !DEMO_MODE && (
        <Alert>
          This page is not served over HTTPS, so the browser will not share your location. Open the official https://
          address of the system.
        </Alert>
      )}

      {!token ? (
        <Card title="1. Scan the QR code">
          <p className="muted">Point the camera at the code shown by your lecturer.</p>
          <QrScanner onResult={acceptText} />
          <div className="divider">or</div>
          <label>
            Paste the code or link
            <input value={pasted} onChange={(e) => setPasted(e.target.value)} placeholder="https://…/scan?token=…" />
          </label>
          <Alert>{pasteError}</Alert>
          <button className="btn btn-secondary" onClick={() => acceptText(pasted)} disabled={!pasted.trim()}>
            Use this code
          </button>
        </Card>
      ) : (
        <Card title="2. Verify your location">
          <p>
            The QR code was read. Your phone will now share its position once, only to confirm that you are in the
            lecture room.
          </p>

          {DEMO_MODE && (
            <fieldset className="demo-box">
              <legend>Demo mode: test coordinates instead of GPS</legend>
              <div className="grid-3">
                <label>
                  Latitude
                  <input value={demo.latitude} onChange={(e) => setDemo({ ...demo, latitude: e.target.value })} />
                </label>
                <label>
                  Longitude
                  <input value={demo.longitude} onChange={(e) => setDemo({ ...demo, longitude: e.target.value })} />
                </label>
                <label>
                  Accuracy (m)
                  <input value={demo.accuracy} onChange={(e) => setDemo({ ...demo, accuracy: e.target.value })} />
                </label>
              </div>
            </fieldset>
          )}

          <Alert>{error}</Alert>
          <div className="row">
            <button className="btn" onClick={checkIn} disabled={busy}>
              {phase === "locating" ? "Finding your position…" : phase === "sending" ? "Checking in…" : "Check in"}
            </button>
            <button className="btn btn-ghost" onClick={() => navigate("/scan", { replace: true })} disabled={busy}>
              Scan a different code
            </button>
          </div>
        </Card>
      )}
    </div>
  );
}
