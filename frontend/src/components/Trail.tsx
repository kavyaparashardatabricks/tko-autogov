import { useEffect, useState } from 'react';
import { getTrail, type TrailEntry, type TrailChanges } from '../api';

const LABEL_COLORS: Record<string, string> = {
  pii: 'bg-red-900/50 text-red-300 border-red-700',
  pci: 'bg-amber-900/50 text-amber-300 border-amber-700',
  confidential: 'bg-purple-900/50 text-purple-300 border-purple-700',
  time_sensitive: 'bg-blue-900/50 text-blue-300 border-blue-700',
};

function LabelPill({ label, count }: { label: string; count: number }) {
  const cls = LABEL_COLORS[label] || 'bg-gray-700 text-gray-300 border-gray-600';
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full border inline-flex items-center gap-1 ${cls}`}>
      {label} <span className="font-bold">{count}</span>
    </span>
  );
}

function StatChip({ icon, value, label }: { icon: string; value: number; label: string }) {
  return (
    <span className="text-[11px] text-gray-400 inline-flex items-center gap-1">
      <span>{icon}</span>
      <span className="font-semibold text-gray-300">{value}</span>
      <span>{label}</span>
    </span>
  );
}

function NoChanges() {
  return (
    <div className="mt-2 flex items-center gap-2 text-xs text-green-400 bg-green-900/20 border border-green-800/40 rounded-md px-3 py-1.5">
      <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
      </svg>
      No new changes detected — all columns match previous scan
    </div>
  );
}

function TrailCard({ entry }: { entry: TrailEntry }) {
  const c = entry.changes_detected as TrailChanges | null;
  const hasChanges = c && (c.new_count > 0 || c.updated_count > 0 || c.deleted_count > 0);
  const hasSuggestions = entry.suggestions && entry.suggestions.length > 0;
  const labelCounts = c?.label_counts || {};
  const labelKeys = Object.keys(labelCounts);

  return (
    <div className="bg-gray-900 rounded-lg px-4 py-3 space-y-2">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <code className="text-xs text-gray-300">{entry.run_id}</code>
          <span className={`text-[10px] px-2 py-0.5 rounded-full ${
            entry.mode === 'agent'
              ? 'bg-orange-900/50 text-orange-300 border border-orange-700'
              : 'bg-indigo-900/50 text-indigo-300 border border-indigo-700'
          }`}>
            {entry.mode}
          </span>
        </div>
        <span className="text-[10px] text-gray-500">
          {new Date(entry.started_at).toLocaleString()}
        </span>
      </div>

      {/* Scan stats row */}
      <div className="flex flex-wrap gap-3">
        <span className="text-[11px] text-gray-500">
          {entry.catalogs === '__all__' ? 'All catalogs' : entry.catalogs}
        </span>
        {c?.tables_scanned != null && (
          <StatChip icon="&#x1f4cb;" value={c.tables_scanned} label="tables" />
        )}
        {c?.columns_scanned != null && (
          <StatChip icon="&#x25a6;" value={c.columns_scanned} label="columns" />
        )}
      </div>

      {/* Diff row */}
      {c && hasChanges && (
        <div className="flex gap-3 text-xs">
          {c.new_count > 0 && (
            <span className="text-green-400">+{c.new_count} new</span>
          )}
          {c.updated_count > 0 && (
            <span className="text-yellow-400">~{c.updated_count} updated</span>
          )}
          {c.deleted_count > 0 && (
            <span className="text-red-400">-{c.deleted_count} deleted</span>
          )}
          {c.classifications_count != null && c.classifications_count > 0 && (
            <span className="text-gray-400">{c.classifications_count} classified</span>
          )}
        </div>
      )}

      {/* Label breakdown */}
      {labelKeys.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {labelKeys.map((label) => (
            <LabelPill key={label} label={label} count={labelCounts[label]} />
          ))}
        </div>
      )}

      {/* Suggestions / applied */}
      {hasSuggestions && (
        <div className="text-xs text-indigo-300">
          {entry.suggestions!.length} recommendation{entry.suggestions!.length !== 1 ? 's' : ''}
        </div>
      )}

      {entry.applied && entry.applied.length > 0 && (
        <div className="text-xs text-orange-400">
          {entry.applied.length} action{entry.applied.length !== 1 ? 's' : ''} applied
        </div>
      )}

      {/* No changes state */}
      {c && !hasChanges && entry.finished_at && <NoChanges />}
    </div>
  );
}

export default function Trail() {
  const [entries, setEntries] = useState<TrailEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = () => {
    setLoading(true);
    getTrail(20)
      .then(setEntries)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="bg-gray-800 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-medium text-gray-300 uppercase tracking-wider">
          Trail Log
        </h2>
        <button
          onClick={refresh}
          className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
        >
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="animate-pulse space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-gray-700 rounded-lg" />
          ))}
        </div>
      ) : entries.length === 0 ? (
        <p className="text-sm text-gray-500">No runs yet. Start a scan above.</p>
      ) : (
        <div className="space-y-2 max-h-[32rem] overflow-y-auto">
          {entries.map((e) => (
            <TrailCard key={e.run_id} entry={e} />
          ))}
        </div>
      )}
    </div>
  );
}
