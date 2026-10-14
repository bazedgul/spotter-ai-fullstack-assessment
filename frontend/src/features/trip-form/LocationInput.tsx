import { useEffect, useId, useRef, useState } from 'react'
import type React from 'react'
import { useQuery } from '@tanstack/react-query'
import { geocode } from '../../api/client'
import type { Location } from '../../api/types'

function placeParts(label: string): { primary: string; secondary: string } {
  const [primary, ...rest] = label.split(',').map((part) => part.trim())
  return { primary, secondary: rest.join(', ') }
}

export function LocationInput({ label, value, onChange }: { label: string; value: Location | null; onChange: (location: Location | null) => void }) {
  const inputId = useId()
  const listId = `${inputId}-suggestions`
  const inputRef = useRef<HTMLInputElement>(null)
  const [text, setText] = useState(value?.label ?? '')
  const [debouncedText, setDebouncedText] = useState('')
  const [active, setActive] = useState(false)
  const [highlighted, setHighlighted] = useState(-1)

  useEffect(() => {
    if (value?.label && value.label !== text) setText(value.label)
  }, [value?.label, text])

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedText(text.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [text])

  const query = useQuery({
    queryKey: ['geocode', debouncedText],
    queryFn: () => geocode(debouncedText),
    enabled: active && debouncedText.length >= 3,
    staleTime: 86_400_000,
  })
  const suggestions = query.data ?? []

  const choose = (location: Location) => {
    setText(location.label)
    setActive(false)
    setHighlighted(-1)
    onChange(location)
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive(true)
      setHighlighted((current) => Math.min(current + 1, suggestions.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setHighlighted((current) => Math.max(current - 1, 0))
    } else if (event.key === 'Enter' && active && highlighted >= 0 && suggestions[highlighted]) {
      event.preventDefault()
      choose(suggestions[highlighted])
    } else if (event.key === 'Escape') {
      setActive(false)
      setHighlighted(-1)
    }
  }

  const showMenu = active && debouncedText.length >= 3
  return <div className="relative">
    <label htmlFor={inputId} className="block text-xs font-medium text-slate-700">{label}
      <input ref={inputRef} id={inputId} role="combobox" aria-label={`${label} search`} aria-autocomplete="list" aria-controls={showMenu ? listId : undefined} aria-expanded={showMenu} aria-activedescendant={highlighted >= 0 ? `${listId}-${highlighted}` : undefined} className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200" value={text} onFocus={() => setActive(true)} onKeyDown={handleKeyDown} onChange={(event) => { setText(event.target.value); setActive(true); setHighlighted(-1); onChange(null) }} placeholder="Search a city or address" />
    </label>
    {showMenu && <div id={listId} role="listbox" className="relative z-30 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-slate-200 bg-white shadow-lg">
      {query.isFetching && <div className="p-3 text-xs text-slate-500">Searching locations...</div>}
      {query.isError && !query.isFetching && <div className="p-3 text-xs text-red-600">Location search failed. Try again.</div>}
      {!query.isFetching && !query.isError && query.isSuccess && suggestions.length === 0 && <div className="p-3 text-xs text-slate-500">No matching locations found.</div>}
      {!query.isFetching && !query.isError && suggestions.map((item, index) => { const parts = placeParts(item.label); return <button id={`${listId}-${index}`} role="option" aria-selected={highlighted === index} type="button" key={`${item.label}-${item.lat}-${item.lon}`} className={`block w-full border-b border-slate-100 px-3 py-2 text-left last:border-0 focus:outline-none ${highlighted === index ? 'bg-emerald-50' : 'hover:bg-slate-50'}`} onMouseDown={(event) => event.preventDefault()} onClick={() => choose(item)}><span className="block text-sm font-semibold text-slate-900">{parts.primary}</span>{parts.secondary && <span className="block text-xs text-slate-500">{parts.secondary}</span>}</button> })}
    </div>}
  </div>
}
