import { Info } from 'lucide-react';

export function DemoBanner() {
  return (
    <div className="demo-banner">
      <Info size={16} />
      <span>
        <strong>Demo Mode:</strong> Displaying simulated data for demonstration purposes.
        Connect your agents to see real metrics.
      </span>
    </div>
  );
}
