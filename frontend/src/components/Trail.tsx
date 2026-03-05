import { useEffect, useState } from 'react';
import { getTrail, type TrailEntry } from '../api';

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
            <div key={i} className="h-12 bg-gray-700 rounded-lg" />
          ))}
        </div>
      ) : entries.length === 0 ? (
        <p className="text-sm text-gray-500">No runs yet. Start a scan above.</p>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {entries.map((e) => (
            <div key={e.run_id} className="bg-gray-900 rounded-lg px-4 py-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <code className="text-xs text-gray-300">{e.run_id}</code>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                    e.mode === 'agent'
                      ? 'bg-orange-900/50 text-orange-300 border border-orange-700'
                      : 'bg-indigo-900/50 text-indigo-300 border border-indigo-700'
                  }`}>
                    {e.mode}
                  </span>
                </div>
                <span className="text-[10px] text-gray-500">
                  {new Date(e.started_at).toLocaleString()}
                </span>
              </div>
              <div className="flex gap-4 mt-2 text-xs text-gray-500">
                <span>Catalog: {e.catalogs}</span>
                {e.changes_detected && (
                  <span>
                    +{e.changes_detected.new_count ?? 0}
                    {' / '}~{e.changes_detected.updated_count ?? 0}
                    {' / '}-{e.changes_detected.deleted_count ?? 0}
                  </span>
                )}
                {e.suggestions && (
                  <span>{e.suggestions.length} suggestion(s)</span>
                )}
                {e.applied && e.applied.length > 0 && (
                  <span className="text-orange-400">{e.applied.length} applied</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
