import { useState, useEffect } from 'react';
import {
  Play,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Copy,
  Loader2,
} from 'lucide-react';
import api from '../services/api';

interface RunSummary {
  run_id: string;
  total_records: number;
  matched: number;
  match_rate: number;
  started_at: string;
}

interface ReconResult {
  id: number;
  run_id: string;
  settlement_id: string | null;
  payment_id: string | null;
  bank_reference: string | null;
  status: string;
  confidence: number;
  expected_amount: number;
  actual_amount: number;
  difference: number;
  matched_by: string;
  evidence: string;
  created_at: string;
}

interface RunDetail {
  run_id: string;
  total_records: number;
  match_rate: number;
  by_status: Record<string, number>;
  by_method: Record<string, number>;
  total_expected: number;
  total_actual: number;
  total_difference: number;
}

const STATUS_CONFIG: Record<string, { color: string; bg: string; icon: any }> = {
  matched: { color: 'text-green-700', bg: 'bg-green-50', icon: CheckCircle2 },
  timing_difference: { color: 'text-amber-700', bg: 'bg-amber-50', icon: Clock },
  amount_mismatch: { color: 'text-orange-700', bg: 'bg-orange-50', icon: AlertTriangle },
  unmatched: { color: 'text-red-700', bg: 'bg-red-50', icon: XCircle },
  missing: { color: 'text-red-700', bg: 'bg-red-50', icon: XCircle },
  duplicate: { color: 'text-purple-700', bg: 'bg-purple-50', icon: Copy },
  requires_review: { color: 'text-amber-700', bg: 'bg-amber-50', icon: AlertTriangle },
};

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(amount);
}

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] || { color: 'text-slate-700', bg: 'bg-slate-50', icon: AlertTriangle };
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${cfg.color} ${cfg.bg}`}>
      <Icon size={12} />
      {status.replace('_', ' ')}
    </span>
  );
}

export default function Reconciliation() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [results, setResults] = useState<ReconResult[]>([]);
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [totalResults, setTotalResults] = useState(0);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadRuns();
  }, []);

  useEffect(() => {
    if (selectedRun) {
      loadDetail(selectedRun);
      loadResults(selectedRun, filterStatus);
    }
  }, [selectedRun, filterStatus]);

  const loadRuns = async () => {
    try {
      const res = await api.get('/reconciliation/runs');
      setRuns(res.data.runs);
      if (res.data.runs.length > 0) {
        setSelectedRun(res.data.runs[0].run_id);
      }
    } catch {}
    setLoading(false);
  };

  const loadDetail = async (runId: string) => {
    try {
      const res = await api.get(`/reconciliation/summary/${runId}`);
      setDetail(res.data);
    } catch {}
  };

  const loadResults = async (runId: string, status: string) => {
    try {
      const params: any = { run_id: runId, limit: 100 };
      if (status) params.status = status;
      const res = await api.get('/reconciliation/results', { params });
      setResults(res.data.results);
      setTotalResults(res.data.total);
    } catch {}
  };

  const handleRun = async () => {
    setRunning(true);
    try {
      const res = await api.post('/reconciliation/run');
      setSelectedRun(res.data.run_id);
      await loadRuns();
    } catch {}
    setRunning(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-blue-600" size={32} />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Reconciliation</h1>
          <p className="text-slate-500 mt-1">Match settlements against bank records</p>
        </div>
        <button
          onClick={handleRun}
          disabled={running}
          className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {running ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
          {running ? 'Running...' : 'Run Reconciliation'}
        </button>
      </div>

      {/* Run selector */}
      {runs.length > 0 && (
        <div className="flex gap-3 mb-6 overflow-x-auto pb-2">
          {runs.map((run) => (
            <button
              key={run.run_id}
              onClick={() => setSelectedRun(run.run_id)}
              className={`flex-shrink-0 px-4 py-3 rounded-lg border text-left transition-colors ${
                selectedRun === run.run_id
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <p className="text-xs text-slate-500 font-mono">{run.run_id}</p>
              <p className="text-sm font-medium mt-1">{run.match_rate}% match rate</p>
              <p className="text-xs text-slate-400">{run.total_records} records</p>
            </button>
          ))}
        </div>
      )}

      {/* Summary cards */}
      {detail && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
            <p className="text-sm text-slate-500">Match Rate</p>
            <p className="text-2xl font-bold text-green-600">{detail.match_rate}%</p>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
            <p className="text-sm text-slate-500">Total Records</p>
            <p className="text-2xl font-bold text-slate-900">{detail.total_records}</p>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
            <p className="text-sm text-slate-500">Expected Total</p>
            <p className="text-lg font-bold text-slate-900">{formatCurrency(detail.total_expected)}</p>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
            <p className="text-sm text-slate-500">Difference</p>
            <p className={`text-lg font-bold ${detail.total_difference > 0 ? 'text-red-600' : 'text-green-600'}`}>
              {formatCurrency(detail.total_difference)}
            </p>
          </div>
        </div>
      )}

      {/* Status breakdown */}
      {detail && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
            <h3 className="font-semibold text-slate-900 mb-3">By Status</h3>
            <div className="space-y-2">
              {Object.entries(detail.by_status).map(([status, count]) => (
                <button
                  key={status}
                  onClick={() => setFilterStatus(filterStatus === status ? '' : status)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${
                    filterStatus === status ? 'bg-blue-50 ring-1 ring-blue-300' : 'hover:bg-slate-50'
                  }`}
                >
                  <StatusBadge status={status} />
                  <span className="font-medium">{count}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
            <h3 className="font-semibold text-slate-900 mb-3">By Match Method</h3>
            <div className="space-y-2">
              {Object.entries(detail.by_method).map(([method, count]) => (
                <div key={method} className="flex items-center justify-between px-3 py-2 text-sm">
                  <span className="text-slate-600">{method.replace('_', ' ')}</span>
                  <span className="font-medium">{count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Results table */}
      {results.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900">
              Results {filterStatus && <span className="text-sm font-normal text-slate-500">— filtered by: {filterStatus}</span>}
            </h3>
            <span className="text-sm text-slate-500">{totalResults} records</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">Status</th>
                  <th className="px-4 py-3 text-left font-medium">Settlement</th>
                  <th className="px-4 py-3 text-left font-medium">Bank Ref</th>
                  <th className="px-4 py-3 text-right font-medium">Expected</th>
                  <th className="px-4 py-3 text-right font-medium">Actual</th>
                  <th className="px-4 py-3 text-right font-medium">Diff</th>
                  <th className="px-4 py-3 text-right font-medium">Confidence</th>
                  <th className="px-4 py-3 text-left font-medium">Method</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {results.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                    <td className="px-4 py-3 font-mono text-xs">{r.settlement_id || r.payment_id || '—'}</td>
                    <td className="px-4 py-3 font-mono text-xs">{r.bank_reference || '—'}</td>
                    <td className="px-4 py-3 text-right">{formatCurrency(r.expected_amount)}</td>
                    <td className="px-4 py-3 text-right">{formatCurrency(r.actual_amount)}</td>
                    <td className={`px-4 py-3 text-right font-medium ${r.difference === 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {formatCurrency(r.difference)}
                    </td>
                    <td className="px-4 py-3 text-right">{(r.confidence * 100).toFixed(0)}%</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{r.matched_by.replace('_', ' ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {runs.length === 0 && !running && (
        <div className="bg-white rounded-xl p-12 shadow-sm border border-slate-200 text-center">
          <Play size={48} className="mx-auto text-slate-300 mb-4" />
          <p className="text-slate-500">No reconciliation runs yet. Click "Run Reconciliation" to start.</p>
        </div>
      )}
    </div>
  );
}
