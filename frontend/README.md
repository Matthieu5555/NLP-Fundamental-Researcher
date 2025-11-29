# George Financial Analyst - Frontend

React + Vite frontend for the George Financial Analyst platform.

## Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build
```

## Environment Variables

Create a `.env` file:

```
VITE_API_URL=http://localhost:5000
```

## Project Structure

```
src/
├── components/
│   ├── StockPicker.jsx      # Stock ticker input
│   ├── AnalysisView.jsx     # Tabbed analysis results
│   └── ChatInterface.jsx    # Chat Q&A interface
├── App.jsx                  # Main single-page layout
└── index.css                # Tailwind CSS
```

## One-Page Flow

1. **Stock Picker** - Enter ticker and start analysis
2. **Analysis View** - Tabs for different analysis sections (Fundamentals, Technicals, Bull/Bear, etc.)
3. **Chat Interface** - Ask questions and get AI responses

All sections appear on a single scrollable page.
