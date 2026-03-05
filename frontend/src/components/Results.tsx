import type { RunResult, Suggestion, AppliedAction } from '../api';

interface Props {
  result: RunResult | null;
}

const LABEL_COLORS: Record<string, string> = {
  pii: 'bg-red-900/50 text-red-300 border-red-700',
  pci: 'bg-amber-900/50 text-amber-300 border-amber-700',
  confidential: 'bg-purple-900/50 text-purple-300 border-purple-700',
  time_sensitive: 'bg-blue-900/50 text-blue-300 border-blue-700',
  public: 'bg-green-900/50 text-green-300 border-green-700',
};

function LabelBadge({ label }: { label: string }) {
  const cls = LABEL_COLORS[label] || 'bg-gray-700 text-gray-300 border-gray-600';
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border ${cls}`}>
      {label}
    </span>
  );
}

export default function Results({ result }: Props) {
  if (!result) return null;

  return (
    <div className="bg-gray-800 rounded-xl p-6 space-y-6">
      {/* Summary */}
      <div>
        <h2 className="text-sm font-medium text-gray-300 uppercase tracking-wider mb-3">
          Run {result.run_id}
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <Stat label="Tables" value={result.tables_scanned} />
          <Stat label="Columns" value={result.columns_scanned} />
          <Stat label="New" value={result.diff.new_count} color="text-green-400" />
          <Stat label="Updated" value={result.diff.updated_count} color="text-yellow-400" />
          <Stat label="Deleted" value={result.diff.deleted_count} color="text-red-400" />
        </div>

        {result.diff.new_count === 0 && result.diff.updated_count === 0 && result.diff.deleted_count === 0 && (
          <div className="flex items-center gap-2 text-sm text-green-400 bg-green-900/20 border border-green-800/40 rounded-lg px-4 py-2 mt-3">
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            No changes since last scan — no new recommendations needed
          </div>
        )}
      </div>

      {/* Suggestions */}
      {result.suggestions.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-400 mb-2">
            Suggestions ({result.suggestions.length})
          </h3>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {result.suggestions.map((s: Suggestion, i: number) => (
              <div key={i} className="bg-gray-900 rounded-lg px-4 py-3">
                <div className="flex items-start justify-between gap-2">
                  <code className="text-xs text-gray-300 break-all">{s.column}</code>
                  <span className="text-xs text-gray-500 whitespace-nowrap">
                    {(s.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {s.labels.map((l) => (
                    <LabelBadge key={l} label={l} />
                  ))}
                </div>
                <div className="flex flex-wrap gap-1 mt-1">
                  {s.recommended_actions.map((a) => (
                    <span key={a} className="text-[10px] text-gray-500 bg-gray-800 px-2 py-0.5 rounded">
                      {a}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Applied actions */}
      {result.applied.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-400 mb-2">
            Applied Actions ({result.applied.length})
          </h3>
          <div className="space-y-1 max-h-60 overflow-y-auto">
            {result.applied.map((a: AppliedAction, i: number) => (
              <div
                key={i}
                className={`text-xs rounded-lg px-3 py-2 ${
                  a.error
                    ? 'bg-red-900/20 text-red-400'
                    : 'bg-gray-900 text-gray-300'
                }`}
              >
                <span className="font-medium">{a.action}</span>
                {' — '}
                {a.column || a.table}
                {a.tag_value && <span className="text-gray-500"> [{a.tag_value}]</span>}
                {a.error && <span className="text-red-400 block mt-1">{a.error}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {result.pii_pci_candidates > 0 && (
        <p className="text-xs text-amber-400 bg-amber-900/20 rounded-lg px-3 py-2">
          {result.pii_pci_candidates} PII/PCI notification candidate(s) stored for future delivery.
        </p>
      )}
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="bg-gray-900 rounded-lg px-3 py-2">
      <div className={`text-xl font-bold ${color || 'text-white'}`}>{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}
