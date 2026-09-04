import { ArrowLeftRight } from 'lucide-react';

export default function Reconciliation() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Reconciliation</h1>
        <p className="text-slate-500 mt-1">Match settlements against transactions</p>
      </div>
      <div className="bg-white rounded-xl p-12 shadow-sm border border-slate-200 text-center">
        <ArrowLeftRight size={48} className="mx-auto text-slate-300 mb-4" />
        <p className="text-slate-500">Reconciliation engine will be available after Phase 4.</p>
      </div>
    </div>
  );
}
