# JARVIS Backend — AI Personal Assistant

Built by Pranadeep Veerabathini
B.Tech AI/ML — Kamala Institute of Technology & Science

## What This Is
The backend server for JARVIS AI Personal Assistant.
Powers the JARVIS EDU OS web application.

## Tech Stack
- Python Flask
- Gemini 1.5 Flash (Primary AI)
- Groq Llama 3.1 (Fallback AI)
- Render.com (24/7 Hosting)

## API Endpoints
- POST /chat — Send message, get AI response
- GET /health — Check server status
- POST /reset — Clear conversation memory

## Environment Variables Required
- GEMINI_API_KEY
- GROQ_API_KEY

## Deployment
Hosted on Render.com — always online 24/7

## Frontend
Hosted on GitHub Pages
Connects to this backend via settings URL
