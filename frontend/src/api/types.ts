export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'SEVERE' | 'NO_TRAVEL' | 'UNKNOWN'

export interface Location { label: string; lat: number; lon: number }
export interface AnalyzeRequest {
  origin: Location; destination: Location; departure_local: string; load_weight_lb: number
  checkpoint_interval_miles: 10 | 25 | 50; simulate_storm?: boolean
}
export interface Checkpoint {
  index: number; mile: number; lat: number; lon: number; eta_utc: string; eta_local: string; tz: string
  owned_miles: number
  weather: { wind_mph: number | null; gust_mph: number | null; rain_in_hr: number | null; snow_in_hr: number | null; status: string }
  risk: { level: RiskLevel; drivers: Array<{ condition: string; level: RiskLevel; note: string }> }
}
export interface RouteMetrics { distance_miles: number; duration_minutes: number; no_travel_miles: number; severe_miles: number; high_miles: number; moderate_miles: number; low_miles: number; unknown_miles: number; avg_risk: number | null; max_level: RiskLevel; blocked: boolean }
export interface RouteResult { id: string; label: string; summary: string; provider?: string; rank: number; recommended: boolean; explanation: string; distance_miles: number; duration_minutes: number; geometry: GeoJSON.LineString; metrics: RouteMetrics; checkpoints: Checkpoint[] }
export interface AnalyzeResponse { request_id: string; departure_utc: string; origin_tz: string; recommended_route_id: string | null; least_risk_route_id: string | null; forecast_available_until: string | null; advisory: string | null; warnings: string[]; routes: RouteResult[]; heatmap_request: unknown; meta: { timings_ms: Record<string, number> } }
export interface HeatmapRequest { routes: Array<{ id: string; polyline: string }>; departure_utc: string; load_weight_lb: number; simulate_storm?: boolean }
export interface HeatmapResponse { hours: 49; features: Array<{ type: 'Feature'; geometry: { type: 'Point'; coordinates: [number, number] }; properties: Record<string, number> }>; warnings: string[] }
