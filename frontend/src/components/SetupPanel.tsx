import { useEffect, useState } from 'react';
import { getCatalogs, getGroups, type GroupInfo } from '../api';

interface Props {
  catalog: string | null;
  setCatalog: (v: string | null) => void;
  mode: 'suggest' | 'agent';
  setMode: (v: 'suggest' | 'agent') => void;
  selectedGroups: string[];
  setSelectedGroups: (v: string[]) => void;
}

export default function SetupPanel({
  catalog, setCatalog,
  mode, setMode,
  selectedGroups, setSelectedGroups,
}: Props) {
  const [catalogs, setCatalogs] = useState<string[]>([]);
  const [groups, setGroups] = useState<GroupInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([getCatalogs(), getGroups()])
      .then(([cats, grps]) => {
        setCatalogs(cats);
        setGroups(grps);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const toggleGroup = (name: string) => {
    setSelectedGroups(
      selectedGroups.includes(name)
        ? selectedGroups.filter((g) => g !== name)
        : [...selectedGroups, name]
    );
  };

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-xl p-6 animate-pulse">
        <div className="h-4 bg-gray-700 rounded w-1/3 mb-4"></div>
        <div className="h-10 bg-gray-700 rounded mb-3"></div>
        <div className="h-10 bg-gray-700 rounded"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/30 border border-red-700 rounded-xl p-6">
        <p className="text-red-400 text-sm">Failed to load workspace data: {error}</p>
        <p className="text-gray-400 text-xs mt-2">
          Make sure the backend is running and DATABRICKS_HOST / DATABRICKS_TOKEN are set.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-xl p-6 space-y-5">
      <h2 className="text-sm font-medium text-gray-300 uppercase tracking-wider">Configuration</h2>

      {/* Catalog selector */}
      <div>
        <label className="block text-sm font-medium text-gray-400 mb-1">Catalog</label>
        <select
          value={catalog ?? '__all__'}
          onChange={(e) => setCatalog(e.target.value === '__all__' ? null : e.target.value)}
          className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="__all__">All catalogs</option>
          {catalogs.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {/* Mode toggle */}
      <div>
        <label className="block text-sm font-medium text-gray-400 mb-2">Mode</label>
        <div className="flex gap-2">
          <button
            onClick={() => setMode('suggest')}
            className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-colors ${
              mode === 'suggest'
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
            }`}
          >
            Suggest Only
          </button>
          <button
            onClick={() => setMode('agent')}
            className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-colors ${
              mode === 'agent'
                ? 'bg-orange-600 text-white'
                : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
            }`}
          >
            Agent (Apply)
          </button>
        </div>
        <p className="text-xs text-gray-500 mt-1">
          {mode === 'suggest'
            ? 'Will scan and suggest tags/policies without applying changes.'
            : 'Will scan, classify, and apply tags + ABAC/RBAC policies automatically.'}
        </p>
      </div>

      {/* Groups (shown in agent mode) */}
      {mode === 'agent' && groups.length > 0 && (
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">
            RBAC Groups ({selectedGroups.length} selected)
          </label>
          <div className="max-h-40 overflow-y-auto space-y-1 bg-gray-900 rounded-lg p-2">
            {groups.map((g) => (
              <label
                key={g.id}
                className="flex items-center gap-2 px-2 py-1 rounded hover:bg-gray-800 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selectedGroups.includes(g.display_name)}
                  onChange={() => toggleGroup(g.display_name)}
                  className="accent-indigo-500"
                />
                <span className="text-sm text-gray-300">{g.display_name}</span>
                <span className="text-xs text-gray-600 ml-auto">{g.member_count} members</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
