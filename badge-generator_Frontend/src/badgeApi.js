// ============================================================================
//  src/badgeApi.js  —  the ONLY file that talks to your FastAPI backend
// ============================================================================
const BASE_URL = window.location.port === "5173"
  ? `http://${window.location.hostname}:8000`
  : "";

// ----------------------------------------------------------------------------
// generateBadge(pdfFile, outerColor, innerColor, partnerLogoFile)
//   Sends the PDF (+ optional colors) and — if the user picked one — the
//   partner logo image, all in one request. The uploaded logo is placed
//   directly onto the badge (no DB lookup needed).
// ----------------------------------------------------------------------------
export async function generateBadge(
  pdfFile,
  outerColor,
  innerColor,
  badgeShape,
  partnerLogoFile
) {
  const form = new FormData();
  form.append("file", pdfFile);
  if (outerColor) form.append("outer_color", outerColor);
  if (innerColor) form.append("inner_color", innerColor);
  if (badgeShape) form.append("badge_shape", badgeShape);
  if (partnerLogoFile) form.append("partner_logo", partnerLogoFile);   // 👈 NEW

  const res = await fetch(`${BASE_URL}/api/generate`, {
    method: "POST",
    body: form,
  });
  return res.json();
}

// ----------------------------------------------------------------------------
// uploadPartnerLogo(partnerName, imageFile)  — optional, saves to PostgreSQL.
// (Kept for when you also want the logo stored in the DB for reuse.)
// ----------------------------------------------------------------------------
export async function uploadPartnerLogo(partnerName, imageFile) {
  const form = new FormData();
  form.append("partner_name", partnerName);
  form.append("file", imageFile);

  const res = await fetch(`${BASE_URL}/api/partner-logo`, {
    method: "POST",
    body: form,
  });
  return res.json();
}
