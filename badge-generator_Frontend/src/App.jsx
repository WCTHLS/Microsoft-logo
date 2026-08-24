import { useState } from "react";
import { generateBadge } from "./badgeApi";
import "./App.css";

const COLOR_OPTIONS = ["teal", "purple", "blue"];
const SHAPE_OPTIONS = ["circle", "diamond"];

export default function App() {
  const [pdfFile, setPdfFile] = useState(null);
  const [status, setStatus] = useState(null);
  const [needsColors, setNeedsColors] = useState(false);
  const [needsShape, setNeedsShape] = useState(false);
  const [outerColor, setOuterColor] = useState("");
  const [innerColor, setInnerColor] = useState("");
  const [badgeShape, setBadgeShape] = useState("");
  const [badgeImage, setBadgeImage] = useState(null);
  const [busy, setBusy] = useState(false);

  const [showModal, setShowModal] = useState(false);
  const [modalStep, setModalStep] = useState("ask");
  const [readyToGenerate, setReadyToGenerate] = useState(false);
  const [logoFile, setLogoFile] = useState(null);

  function handlePdfChange(event) {
    const file = event.target.files[0] || null;

    setPdfFile(file);
    setStatus(null);
    setNeedsColors(false);
    setNeedsShape(false);
    setOuterColor("");
    setInnerColor("");
    setBadgeShape("");
    setBadgeImage(null);
    setReadyToGenerate(false);
    setLogoFile(null);

    if (file) {
      setModalStep("ask");
      setShowModal(true);
    }
  }

  function handleNoLogo() {
    setLogoFile(null);
    setShowModal(false);
    setReadyToGenerate(true);
  }

  function handleYesLogo() {
    setModalStep("upload");
  }

  function handleLogoSelected(event) {
    const file = event.target.files[0] || null;

    if (!file) {
      return;
    }

    setLogoFile(file);
    setShowModal(false);
    setReadyToGenerate(true);
  }

  function handleSkipLogo() {
    setLogoFile(null);
    setShowModal(false);
    setReadyToGenerate(true);
  }

  async function handleGenerate() {
    if (!pdfFile) {
      return;
    }

    setBusy(true);
    setStatus(null);

    try {
      const data = await generateBadge(
        pdfFile,
        outerColor,
        innerColor,
        badgeShape,
        logoFile
      );

      if (data.valid) {
        setStatus({
          type: "ok",
          message: data.message,
        });
        setBadgeImage(data.image_base64);
        setNeedsColors(false);
        setNeedsShape(false);
      } else {
        setStatus({
          type: "err",
          message: data.message,
        });
        setNeedsColors(Boolean(data.needs_colors));
        setNeedsShape(Boolean(data.needs_shape));
        setBadgeImage(null);
      }
    } catch (error) {
      setStatus({
        type: "err",
        message: "Could not reach the server. Is it running?",
      });
      setBadgeImage(null);
    } finally {
      setBusy(false);
    }
  }

  function handleDownload() {
    if (!badgeImage) {
      return;
    }

    const link = document.createElement("a");
    link.href = `data:image/png;base64,${badgeImage}`;
    link.download = "badge_generated.png";
    link.click();
  }

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <MicrosoftLogo />
          <span className="divider" />
          <span className="product">Badge Generator</span>
        </div>
      </header>

      <main className="workspace">
        <div className="hero">
          <h1>Generate your badge</h1>
          <p>
            Upload a badge PDF to validate the design and generate a
            print-ready badge.
          </p>
        </div>

        <section className="panel">
          <label className="dropzone">
            <input
              type="file"
              accept="application/pdf"
              onChange={handlePdfChange}
              hidden
            />

            <div className="dropzone-inner">
              <UploadIcon />

              {pdfFile ? (
                <>
                  <strong className="file-name">
                    {pdfFile.name}
                  </strong>
                  <span className="dropzone-subtitle">
                    Click to choose a different file
                  </span>
                </>
              ) : (
                <>
                  <strong>Click to upload a PDF</strong>
                  <span className="dropzone-subtitle">
                    Only PDF files are supported
                  </span>
                </>
              )}
            </div>
          </label>

          {logoFile && (
            <div className="selected-logo">
              <span>Partner logo</span>
              <strong>{logoFile.name}</strong>
            </div>
          )}

          {needsColors && (
            <div className="colors">
              <p className="colors-title">
                Colors were not detected. Select the badge colors.
              </p>

              <div className="colors-row">
                <label className="field">
                  <span>Outer color</span>
                  <select
                    value={outerColor}
                    onChange={(event) =>
                      setOuterColor(event.target.value)
                    }
                  >
                    <option value="">Select</option>
                    {COLOR_OPTIONS.map((color) => (
                      <option key={color} value={color}>
                        {color}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span>Inner color</span>
                  <select
                    value={innerColor}
                    onChange={(event) =>
                      setInnerColor(event.target.value)
                    }
                  >
                    <option value="">Select</option>
                    {COLOR_OPTIONS.map((color) => (
                      <option key={color} value={color}>
                        {color}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          )}

          {needsShape && (
            <div className="colors">
              <p className="colors-title">
                Shape was not detected. Select the badge shape.
              </p>
              <div className="colors-row">
                <label className="field">
                  <span>Badge shape</span>
                  <select
                    value={badgeShape}
                    onChange={(event) => setBadgeShape(event.target.value)}
                  >
                    <option value="">Select</option>
                    {SHAPE_OPTIONS.map((shape) => (
                      <option key={shape} value={shape}>
                        {shape.charAt(0).toUpperCase() + shape.slice(1)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          )}
          <button
            className="button-primary"
            onClick={handleGenerate}
            disabled={!pdfFile || !readyToGenerate || busy}
          >
            {busy ? "Generating..." : "Generate Badge"}
          </button>

          {status && (
            <div className={`status-banner ${status.type}`}>
              <span className="status-icon">
                {status.type === "ok" ? "✓" : "!"}
              </span>
              <p>{status.message}</p>
            </div>
          )}
        </section>

        {badgeImage && (
          <section className="result-panel">
            <div className="result-preview">
              <img
                src={`data:image/png;base64,${badgeImage}`}
                alt="Generated badge"
              />
            </div>

            <div className="result-actions">
              <h2>Your badge is ready</h2>
              <button
                className="button-primary"
                onClick={handleDownload}
              >
                Download Badge
              </button>
            </div>
          </section>
        )}
      </main>

      {showModal && (
        <div className="modal-overlay">
          <div className="modal" role="dialog" aria-modal="true">
            {modalStep === "ask" ? (
              <>
                <h3>Upload a partner logo?</h3>
                <p className="modal-text">
                  Does this badge include a partner logo?
                </p>

                <div className="modal-actions">
                  <button
                    className="button-secondary"
                    onClick={handleNoLogo}
                  >
                    No
                  </button>
                  <button
                    className="button-primary compact"
                    onClick={handleYesLogo}
                  >
                    Yes
                  </button>
                </div>
              </>
            ) : (
              <>
                <h3>Upload partner logo</h3>
                <p className="modal-text">
                  Select the partner logo image to include on the badge.
                </p>

                <label className="dropzone small">
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleLogoSelected}
                    hidden
                  />
                  <div className="dropzone-inner">
                    <strong>Click to choose an image</strong>
                  </div>
                </label>

                <div className="modal-actions">
                  <button
                    className="button-secondary"
                    onClick={handleSkipLogo}
                  >
                    Skip
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function MicrosoftLogo() {
  return (
    <div className="microsoft-logo" aria-label="Microsoft">
      <div className="microsoft-symbol">
        <span style={{ background: "#F25022" }} />
        <span style={{ background: "#7FBA00" }} />
        <span style={{ background: "#00A4EF" }} />
        <span style={{ background: "#FFB900" }} />
      </div>
      <span className="microsoft-text">Microsoft</span>
    </div>
  );
}

function UploadIcon() {
  return (
    <svg
      width="40"
      height="40"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#0078d4"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}
