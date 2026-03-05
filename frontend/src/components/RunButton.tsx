import { useState } from 'react';
import { startRun, type RunRequest, type RunResult } from '../api';

interface Props {
  catalog: string | null;
  mode: 'suggest' | 'agent';
  selectedGroups: string[];
  onResult: (r: RunResult) => void;
}

export default function RunButton({ catalog, mode, selectedGroups, onResult }: Props) {
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');

  const handleRun = async () => {
    setRunning(true);
    setError('');
    try {
      const body: RunRequest = {
        catalog,
        mode,
        group_names: mode === 'agent' ? selectedGroups : undefined,
      };
      const result = await startRun(body);
      onResult(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-2">
      <button
        onClick={handleRun}
        disabled={running}
        className={`w-full py-3 rounded-lg font-medium text-sm transition-all ${
          running
            ? 'bg-gray-700 text-gray-400 cursor-wait'
            : mode === 'agent'
              ? 'bg-orange-600 hover:bg-orange-500 text-white'
              : 'bg-indigo-600 hover:bg-indigo-500 text-white'
        }`}
      >
        {running ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Scanning...
          </span>
        ) : mode === 'agent' ? (
          'Run Scan & Apply'
        ) : (
          'Run Scan'
        )}
      </button>
      {error && (
        <p className="text-red-400 text-xs bg-red-900/20 rounded-lg px-3 py-2">{error}</p>
      )}
    </div>
  );
}
