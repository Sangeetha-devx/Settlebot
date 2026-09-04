import { FileText } from 'lucide-react';

export default function Settlements() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Settlements</h1>
        <p className="text-slate-500 mt-1">Investigate settlement breakdowns</p>
      </div>
      <div className="bg-white rounded-xl p-12 shadow-sm border border-slate-200 text-center">
        <FileText size={48} className="mx-auto text-slate-300 mb-4" />
        <p className="text-slate-500">Settlement investigation will be available after Phase 8.</p>
      </div>
    </div>
  );
}
