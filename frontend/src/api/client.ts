import type { AnalyzeRequest, AnalyzeResponse, HeatmapRequest, HeatmapResponse, Location } from './types'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${url}`, { headers: { 'Content-Type': 'application/json' }, ...init })
  const body = await response.json() as T | { error?: { message?: string } }
  if (!response.ok) throw new Error((body as { error?: { message?: string } }).error?.message ?? 'Request failed')
  return body as T
}
export const analyzeTrip = async (payload: AnalyzeRequest) => {
  const result = await request<AnalyzeResponse>('/api/analyze', { method: 'POST', body: JSON.stringify(payload) })
  sessionStorage.setItem('trucksafe_departure_utc', result.departure_utc)
  if (result.forecast_available_until) sessionStorage.setItem('trucksafe_forecast_until', result.forecast_available_until)
  return result
}
export const geocode = (query: string) => request<Location[]>(`/api/geocode?q=${encodeURIComponent(query)}`)
export const fetchHeatmap = (payload: HeatmapRequest) => request<HeatmapResponse>('/api/heatmap', { method: 'POST', body: JSON.stringify(payload) })
