#!/bin/bash

# Start Backend
echo "Starting Backend..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# Start Frontend
echo "Starting Frontend..."
cd ../frontend
npm install
npm run dev &
FRONTEND_PID=$!

echo "Systems initialized."
echo "Backend running on http://localhost:8000"
echo "Frontend running on http://localhost:5173"

# Wait for exit
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT TERM
wait
