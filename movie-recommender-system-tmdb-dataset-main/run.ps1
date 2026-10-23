Write-Host "========================================================" -ForegroundColor Red
Write-Host "  NETFLIX-STYLE AI MOVIE RECOMMENDER SYSTEM" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Red
Write-Host ""
Write-Host "Starting FastAPI Application on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
& python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
