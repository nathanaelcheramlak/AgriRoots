# Farmly Frontend (React + Vite)

This frontend is now built with React, Vite, and Tailwind CSS.

## Setup

1. Install dependencies:

```bash
npm install
```

2. Create local env file:

```bash
cp .env.example .env.local
```

If `cp` is not available on Windows PowerShell:

```powershell
Copy-Item .env.example .env.local
```

3. Start development server:

```bash
npm run dev
```

The app runs at `http://localhost:3000`.

## Build

```bash
npm run build
npm run preview
```

## Environment Variables

- `VITE_API_BASE_URL` (default: `http://127.0.0.1:8000`)
- `VITE_DEBUG` (`true` or `false`)
