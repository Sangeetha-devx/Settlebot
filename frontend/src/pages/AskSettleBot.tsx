import { MessageSquare } from 'lucide-react';

export default function AskSettleBot() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Ask SettleBot</h1>
        <p className="text-slate-500 mt-1">Chat with the AI finance agent</p>
      </div>
      <div className="bg-white rounded-xl p-12 shadow-sm border border-slate-200 text-center">
        <MessageSquare size={48} className="mx-auto text-slate-300 mb-4" />
        <p className="text-slate-500">AI agent will be available after Phase 9.</p>
      </div>
    </div>
  );
}
