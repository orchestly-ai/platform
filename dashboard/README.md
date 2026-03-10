# Orchestly Dashboard

Real-time monitoring dashboard for the Orchestly Platform.

## Features

- **Live Metrics**: Real-time system metrics with 5-second auto-refresh
- **Agent Monitoring**: Status, utilization, and performance tracking for all registered agents
- **Task Queue Visualization**: Monitor task queue depth by capability
- **Cost Tracking**: Track API costs (today, this month) with trend charts
- **Alert Management**: Critical, warning, and info alerts with severity-based filtering
- **Success Rate Analytics**: Task completion and failure metrics with visualizations

## Tech Stack

- **React 18.2** with TypeScript
- **Vite** - Lightning-fast build tool and dev server
- **TailwindCSS 3.3** - Utility-first CSS framework
- **React Router 6.20** - Client-side routing
- **TanStack Query 5.14** - Data fetching with automatic caching and refetching
- **Recharts 2.10** - Responsive chart library
- **Lucide React** - Beautiful icon library
- **date-fns** - Modern date utility library

## Prerequisites

- Node.js 16+ and npm
- Running Orchestly Platform backend on `http://localhost:8000`

## Installation

```bash
# Install dependencies
npm install
```

## Development

```bash
# Start development server on http://localhost:3000
npm run dev
```

The development server includes:
- Hot module replacement (HMR) for instant updates
- API proxy to backend (`/api` → `http://localhost:8000`)
- Auto-refresh every 5 seconds for real-time data

## Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Configuration

### API Base URL

The dashboard communicates with the backend API. By default, Vite proxies `/api` requests to `http://localhost:8000`.

To change the backend URL, update `vite.config.ts`:

```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://your-backend-url:8000',
        changeOrigin: true,
      },
    },
  },
})
```

### Auto-refresh Interval

Data automatically refreshes every 5 seconds. To change this, update `src/main.tsx`:

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 5000, // milliseconds
    },
  },
})
```

## Project Structure

```
dashboard/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── Layout.tsx       # Main layout with navigation
│   │   ├── MetricsCard.tsx  # Metric display card
│   │   ├── AgentStatusGrid.tsx  # Agent monitoring grid
│   │   ├── QueueVisualization.tsx  # Queue depth bars
│   │   ├── CostChart.tsx    # Cost trend line chart
│   │   ├── TaskSuccessChart.tsx  # Success/failure bar chart
│   │   └── AlertBanner.tsx  # Alert notification banner
│   ├── pages/               # Page components
│   │   ├── Dashboard.tsx    # Main dashboard page
│   │   ├── Agents.tsx       # Agents monitoring page
│   │   ├── Tasks.tsx        # Task queue page
│   │   └── Alerts.tsx       # Alert management page
│   ├── lib/
│   │   └── api.ts           # API client
│   ├── types/
│   │   └── index.ts         # TypeScript interfaces
│   ├── App.tsx              # Root component with routing
│   ├── main.tsx             # Entry point
│   └── index.css            # Global styles
├── public/                  # Static assets
├── index.html               # HTML template
├── vite.config.ts           # Vite configuration
├── tailwind.config.js       # Tailwind configuration
└── tsconfig.json            # TypeScript configuration
```

## API Endpoints

The dashboard expects the following backend API endpoints:

- `GET /api/metrics/system` - System metrics (agents, tasks, queues, costs)
- `GET /api/metrics/timeseries?metric={metric}&duration={minutes}` - Time-series data
- `GET /api/alerts` - Active alerts
- `GET /api/alerts/stats` - Alert statistics

## Pages

### Dashboard (`/dashboard`)
Overview of the entire system with:
- Key metrics cards (active agents, tasks, costs)
- Task success rate chart
- Cost trend chart
- Agent status grid
- Queue visualization
- Alert banner

### Agents (`/agents`)
Detailed view of all registered agents:
- Agent status (active, idle, error)
- Active tasks count
- Completed/failed tasks
- Cost per agent
- Last seen timestamp

### Tasks (`/tasks`)
Task queue monitoring:
- Queue depth visualization
- Tasks by capability
- Dead letter queue alerts
- (Coming soon: Task history and logs)

### Alerts (`/alerts`)
Alert management dashboard:
- Alert statistics (active, critical, warning, last 24h)
- Active alerts list
- Severity-based filtering
- Time-based grouping

## Customization

### Tailwind Theme

Customize colors, fonts, and spacing in `tailwind.config.js`:

```javascript
export default {
  theme: {
    extend: {
      colors: {
        // Add custom colors
      },
    },
  },
}
```

### Custom CSS Variables

Global CSS variables are defined in `src/index.css`:

```css
:root {
  --status-active: #10b981;
  --status-idle: #f59e0b;
  --status-error: #ef4444;
}
```

## Troubleshooting

### Dashboard shows "Loading..." indefinitely

- Ensure the backend is running on `http://localhost:8000`
- Check browser console for API errors
- Verify API endpoints are responding correctly

### Data not updating

- Check `refetchInterval` in `src/main.tsx`
- Verify network tab in browser dev tools shows periodic requests
- Ensure backend is returning fresh data

### Charts not rendering

- Ensure data format matches expected structure in components
- Check for null/undefined data in browser console
- Verify Recharts components are receiving proper props

## Development Tips

- Use React DevTools to inspect component state and props
- Enable TanStack Query DevTools for debugging queries (uncomment in `src/main.tsx`)
- Hot reload works for most changes; restart dev server if needed
- TypeScript errors will show in terminal and browser

## License

Part of the Orchestly Platform
