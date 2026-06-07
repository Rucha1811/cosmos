---
title: Card Scanner
emoji: 🃏
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: false
---

# Card Scanner

PaddleOCR-based card scanning web app. Upload a card image, extract text, fill structured fields, export CSV.

## API Endpoints

- `GET /` — Web UI
- `POST /api/scan` — Upload and OCR a card image
- `GET /api/scans` — List all scans
- `PATCH /api/scans/<uuid>` — Save card details
- `DELETE /api/scans/<uuid>` — Delete a scan
- `GET /api/export/csv` — Export as CSV
- `DELETE /api/clear` — Clear all scans
