import { useEffect, useState } from 'react';
import {
  IndianRupee,
  ArrowDownRight,
  ArrowUpRight,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import api from '../services/api';

interface Summary {
  gross_revenue: number;
  net_revenue: number;
  settled_amount: number;
  pending_amount: number;
  total_refunds: number;
  total_chargebacks: number;
  reconciliation_percentage: number;
  matched_records: number;
  unmatched_records: number;
  critical_exceptions: number;
  total_payments: number;
  total_settlements: number;
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount);
}

function StatCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  icon: any;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    amber: 'bg-amber-50 text-amber-600',
    red: 'bg-red-50 text-red-600',
    slate: 'bg-slate-50 text-slate-600',
  };

  return (
    <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-slate-500">{label}</span>
        <div className={`p-2 rounded-lg ${colorMap[color] || colorMap.slate}`}>
          <Icon size={18} />
        </div>
      </div>
      <p className="text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/dashboard/summary')
      .then((res) => setSummary(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="text-center text-slate-500 mt-20">
        <p>No data available. Run synthetic data generation first (Phase 1).</p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-slate-500 mt-1">Financial overview and reconciliation status</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Gross Revenue" value={formatCurrency(summary.gross_revenue)} icon={IndianRupee} color="blue" />
        <StatCard label="Net Revenue" value={formatCurrency(summary.net_revenue)} icon={ArrowUpRight} color="green" />
        <StatCard label="Settled Amount" value={formatCurrency(summary.settled_amount)} icon={CheckCircle2} color="green" />
        <StatCard label="Pending Settlement" value={formatCurrency(summary.pending_amount)} icon={Clock} color="amber" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Total Refunds" value={formatCurrency(summary.total_refunds)} icon={ArrowDownRight} color="amber" />
        <StatCard label="Chargebacks" value={formatCurrency(summary.total_chargebacks)} icon={XCircle} color="red" />
        <StatCard label="Match Rate" value={`${summary.reconciliation_percentage}%`} icon={CheckCircle2} color="green" />
        <StatCard label="Critical Exceptions" value={String(summary.critical_exceptions)} icon={AlertTriangle} color="red" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
          <h3 className="font-semibold text-slate-900 mb-3">Reconciliation Summary</h3>
          <div className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Matched Records</span>
              <span className="font-medium text-green-600">{summary.matched_records}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Unmatched Records</span>
              <span className="font-medium text-red-600">{summary.unmatched_records}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Total Payments</span>
              <span className="font-medium">{summary.total_payments}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Total Settlements</span>
              <span className="font-medium">{summary.total_settlements}</span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-200 lg:col-span-2">
          <h3 className="font-semibold text-slate-900 mb-3">Quick Actions</h3>
          <div className="grid grid-cols-2 gap-3">
            <a href="/reconciliation" className="block p-4 rounded-lg bg-blue-50 hover:bg-blue-100 transition-colors text-center">
              <p className="font-medium text-blue-700 text-sm">Run Reconciliation</p>
            </a>
            <a href="/exceptions" className="block p-4 rounded-lg bg-amber-50 hover:bg-amber-100 transition-colors text-center">
              <p className="font-medium text-amber-700 text-sm">View Exceptions</p>
            </a>
            <a href="/forecast" className="block p-4 rounded-lg bg-green-50 hover:bg-green-100 transition-colors text-center">
              <p className="font-medium text-green-700 text-sm">Cash Forecast</p>
            </a>
            <a href="/ask" className="block p-4 rounded-lg bg-purple-50 hover:bg-purple-100 transition-colors text-center">
              <p className="font-medium text-purple-700 text-sm">Ask SettleBot</p>
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
