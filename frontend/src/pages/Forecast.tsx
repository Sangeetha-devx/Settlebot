import { TrendingUp } from 'lucide-react';

export default function Forecast() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Cash Forecast</h1>
        <p className="text-slate-500 mt-1">1-day, 3-day, and 7-day cash flow projections</p>
      </div>
      <div className="bg-white rounded-xl p-12 shadow-sm border border-slate-200 text-center">
        <TrendingUp size={48} className="mx-auto text-slate-300 mb-4" />
        <p className="text-slate-500">Cash forecasting will be available after Phase 11.</p>
      </div>
    </div>
  );
}
