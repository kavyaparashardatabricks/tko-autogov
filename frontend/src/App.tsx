import { useState } from 'react';
import Header from './components/Header';
import SetupPanel from './components/SetupPanel';
import RunButton from './components/RunButton';
import Results from './components/Results';
import Trail from './components/Trail';
import type { RunResult } from './api';

export default function App() {
  const [catalog, setCatalog] = useState<string | null>(null);
  const [mode, setMode] = useState<'suggest' | 'agent'>('suggest');
  const [selectedGroups, setSelectedGroups] = useState<string[]>([]);
  const [result, setResult] = useState<RunResult | null>(null);
  const [trailKey, setTrailKey] = useState(0);

  const handleResult = (r: RunResult) => {
    setResult(r);
    setTrailKey((k) => k + 1);
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Header />
      <main className="max-w-7xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: setup + run */}
        <div className="space-y-4">
          <SetupPanel
            catalog={catalog}
            setCatalog={setCatalog}
            mode={mode}
            setMode={setMode}
            selectedGroups={selectedGroups}
            setSelectedGroups={setSelectedGroups}
          />
          <RunButton
            catalog={catalog}
            mode={mode}
            selectedGroups={selectedGroups}
            onResult={handleResult}
          />
        </div>

        {/* Right column: results + trail */}
        <div className="lg:col-span-2 space-y-6">
          <Results result={result} />
          <Trail key={trailKey} />
        </div>
      </main>
    </div>
  );
}
