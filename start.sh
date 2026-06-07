#!/bin/bash
echo "========================================================"
echo "  Card Scanner - PaddleOCR Web App"
echo "========================================================"
echo ""
echo "  Starting server..."
echo "  Open browser at: http://127.0.0.1:5050"
echo ""
echo "  * Upload a card image to scan"
echo "  * View extracted text with confidence scores"
echo "  * Export all scans as CSV"
echo "========================================================"
echo ""

/opt/homebrew/bin/python3.11 /Users/ruchatejaskumargandhi/Desktop/card-scanner/backend/app.py
