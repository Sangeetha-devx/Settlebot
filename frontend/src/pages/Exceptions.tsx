import { AlertTriangle } from 'lucide-react';

export default function Exceptions() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Exceptions</h1>
        <p className="text-slate-500 mt-1">Review flagged discrepancies and anomalies</p>
      </div>
      <div className="bg-white rounded-xl p-12 shadow-sm border border-slate-200 text-center">
        <AlertTriangle size={48} className="mx-auto text-slate-300 mb-4" />
        <p className="text-slate-500">Exception engine will be available after Phase 6.</p>
      </div>
    </div>
  );
}
