# Library Assistant Frontend

Frontend application for the Library Assistant built with vanilla JavaScript, Tailwind CSS, and Vite.

## Prerequisites

- Node.js (v16 or higher)
- npm (comes with Node.js)

## Setup

1. Install dependencies:
```bash
npm install
```

## Development

Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

Vite provides:
- Hot Module Replacement (HMR) - changes reflect instantly
- Fast builds
- ES module support
- Optimized production builds

## Build for Production

Build the frontend for production:
```bash
npm run build
```

The built files will be in the `dist/` directory.

## Preview Production Build

Preview the production build locally:
```bash
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── components/     # Reusable components (header, chat-widget)
│   ├── services/       # API service layer
│   ├── pages/          # Page-specific JavaScript
│   └── styles/         # Additional styles
├── public/             # Static assets
├── index.html          # Home page
├── catalog.html        # Book catalog page
├── book-details.html   # Book details page
├── my-books.html       # My books page
├── package.json        # npm dependencies and scripts
└── vite.config.js     # Vite configuration
```

## Backend Connection

The frontend connects to the backend API at `http://localhost:8000` by default. Make sure the backend is running before starting the frontend.

To change the API URL, edit `src/services/api.js` and update the `API_BASE_URL` constant.

