export default function Header() {
  return (
    <header className="bg-gray-900 text-white border-b border-gray-700">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center font-bold text-sm">
          FG
        </div>
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Finance Governance</h1>
          <p className="text-xs text-gray-400">Unity Catalog tag & policy automation</p>
        </div>
      </div>
    </header>
  );
}
