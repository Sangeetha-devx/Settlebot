import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  ArrowLeftRight,
  AlertTriangle,
  MessageSquare,
  TrendingUp,
  FileText,
  LogOut,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/reconciliation', icon: ArrowLeftRight, label: 'Reconciliation' },
  { to: '/exceptions', icon: AlertTriangle, label: 'Exceptions' },
  { to: '/settlements', icon: FileText, label: 'Settlements' },
  { to: '/forecast', icon: TrendingUp, label: 'Cash Forecast' },
  { to: '/ask', icon: MessageSquare, label: 'Ask SettleBot' },
];

export default function Sidebar() {
  const { logout, user } = useAuth();

  return (
    <aside className="w-64 bg-slate-900 text-white flex flex-col min-h-screen">
      <div className="p-6 border-b border-slate-700">
        <h1 className="text-xl font-bold tracking-tight">SettleBot</h1>
        <p className="text-xs text-slate-400 mt-1">AI Finance Controller</p>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              }`
            }
          >
            <item.icon size={18} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-slate-700">
        <div className="flex items-center justify-between">
          <div className="text-sm">
            <p className="text-slate-300 font-medium">{user?.username}</p>
            <p className="text-slate-500 text-xs">{user?.role}</p>
          </div>
          <button
            onClick={logout}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </aside>
  );
}
