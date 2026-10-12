import React from 'react'
import { Navigation, ShieldCheck } from 'lucide-react'

export function App() {
  return (
    <div className="flex h-screen w-screen flex-col bg-slate-50 text-slate-900">
      <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-6 shadow-sm">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-6 w-6 text-emerald-600" />
          <h1 className="text-lg font-bold tracking-tight text-slate-800">
            TruckSafe <span className="text-xs font-medium text-slate-500">Weather-Aware Routing</span>
          </h1>
        </div>
        <div className="flex items-center gap-4 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <Navigation className="h-3.5 w-3.5" /> Ready
          </span>
        </div>
      </header>

      <main className="flex flex-1 overflow-hidden">
        <aside className="w-96 border-r border-slate-200 bg-white p-4 overflow-y-auto">
          <h2 className="text-sm font-semibold text-slate-700">Trip Configuration</h2>
          <p className="mt-1 text-xs text-slate-500">
            Select origin, destination, departure time, and load weight.
          </p>
        </aside>

        <section className="flex-1 bg-slate-100 p-4">
          <div className="flex h-full items-center justify-center rounded-lg border-2 border-dashed border-slate-300 text-sm text-slate-400">
            Map Container Placeholder
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 bg-white px-4 py-2 text-[11px] text-slate-500 flex justify-between">
        <span>Weather data by Open-Meteo.com (CC BY 4.0) | Map tiles by Carto (OSM)</span>
        <span className="text-slate-400">Informational safety decision support only. Not certified dispatch advice.</span>
      </footer>
    </div>
  )
}

export default App
