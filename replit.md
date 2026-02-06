# Marda Loop Bakery

## Overview

This is a Telegram Mini App (WebApp) for a bakery called "Marda Loop Bakery." It allows customers to browse a menu, add items to a cart, and place orders directly through Telegram. The project has two main runtime components:

1. **A Flask web server** (`app.py`) that serves the frontend (static HTML/JS) and provides a REST API for order management.
2. **A Telegram bot** (`bot.py`) that uses aiogram to integrate with Telegram's Bot API, presenting users with a button to open the web app and handling order data sent back from it.

The frontend is a single-page application built with vanilla HTML/JS, styled with Tailwind CSS (via CDN), and integrated with Telegram's WebApp JS SDK.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend
- **Single HTML file** (`index.html`) served as a static file by Flask. Uses Tailwind CSS via CDN for styling, Font Awesome for icons, and Google Fonts (Outfit).
- **Telegram WebApp SDK** (`telegram-web-app.js`) is loaded to enable communication between the mini app and the Telegram client (sending order data back to the bot).
- **Menu data** is loaded from `menu.json` — a static JSON file with item details (name, price, category, type, image URL). Images are hosted on Unsplash.
- Categories include: pastry, drinks, lunch. Items have a "type" field (warm/cold) which appears to be used for weather-based recommendations.
- The app has a weather debug feature in the header, suggesting weather-aware menu suggestions.

### Backend — Flask (`app.py`)
- Serves static files (HTML, JSON) from the project root directory.
- **POST `/api/order`** — Accepts order JSON, appends to `orders.json` file, returns order ID and status.
- **GET `/menu.json`** — Serves the menu data.
- **GET `/`** — Serves `index.html`.
- Orders are stored in a flat `orders.json` file (no database). This is simple file-based persistence — not suitable for production but fine for a demo.
- The Flask server runs on port 5000 by default (configurable via `PORT` env var).

### Backend — Telegram Bot (`bot.py`)
- Uses **aiogram 3.x** (async Telegram bot framework for Python).
- Responds to `/start` with a reply keyboard containing a WebApp button that opens the Flask-served frontend.
- Handles `WEB_APP_DATA` content type — when the user completes an order in the mini app, Telegram sends the data to the bot, which parses it and confirms the order.
- Runs independently from Flask using `asyncio` polling.

### Runtime Model
- **Two separate processes** need to run simultaneously:
  1. Flask web server (`app.py`) — serves the web UI and API
  2. Telegram bot (`bot.py`) — handles Telegram interactions
- Both are Python scripts started independently.

### Data Storage
- **`menu.json`** — Static menu catalog. Read-only.
- **`orders.json`** — Append-only order log. Simple JSON array stored on disk. No database is used. Order IDs are derived from array length (not collision-safe).
- No database (no Drizzle, no Postgres, no SQLite). If scaling is needed, a proper database should replace the JSON file approach.

### Environment Variables
| Variable | Purpose |
|---|---|
| `TELEGRAM_TOKEN` | Bot API token from @BotFather (required) |
| `WEBAPP_URL` | Public URL of the Flask app, used in the Telegram keyboard button (defaults to `http://localhost:5000`) |
| `PORT` | Flask server port (defaults to 5000) |

### Key Design Decisions
- **No build step** — The frontend uses CDN-loaded libraries (Tailwind, Font Awesome) and vanilla JS. No bundler, no Node.js required.
- **File-based storage over database** — Chosen for simplicity in a demo context. The tradeoff is no concurrent write safety and no query capabilities.
- **Two-process architecture** — Flask and the Telegram bot run as separate Python processes. They share data through the filesystem (`orders.json`). An alternative would be combining them into one process, but keeping them separate is cleaner for this use case.
- **aiogram 3.x** — Modern async Telegram framework chosen over alternatives like python-telegram-bot. Uses polling mode (not webhooks), which is simpler for development.

## External Dependencies

### Python Packages (requirements.txt)
- **Flask 3.0.3** — Web framework for serving the frontend and API
- **aiogram 3.13.1** — Async Telegram Bot API framework

### External Services
- **Telegram Bot API** — Core integration; requires a bot token from @BotFather
- **Telegram WebApp SDK** — JS library loaded from `telegram.org` for mini app integration
- **Unsplash** — Menu item images are hotlinked from Unsplash CDN

### CDN Resources
- **Tailwind CSS** — Loaded via `cdn.tailwindcss.com`
- **Font Awesome 6.0.0** — Icon library via cdnflare
- **Google Fonts (Outfit)** — Typography