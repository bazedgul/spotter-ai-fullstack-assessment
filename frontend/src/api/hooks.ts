import { useMutation, useQuery } from '@tanstack/react-query'
import { analyzeTrip, fetchHeatmap } from './client'
import type { AnalyzeRequest, HeatmapRequest } from './types'
export function useAnalyzeTrip() { return useMutation({ mutationFn: (payload: AnalyzeRequest) => analyzeTrip(payload) }) }
export function useHeatmap(payload: HeatmapRequest | null) { return useQuery({ queryKey: ['heatmap', payload], queryFn: () => fetchHeatmap(payload as HeatmapRequest), enabled: payload !== null, staleTime: Infinity }) }
