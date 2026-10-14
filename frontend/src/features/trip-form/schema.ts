import { z } from 'zod'
export const tripSchema = z.object({
  origin: z.object({ label: z.string().min(2, 'Enter an origin'), lat: z.number(), lon: z.number() }).refine((v) => v.lat !== 0 || v.lon !== 0, 'Select an origin suggestion'),
  destination: z.object({ label: z.string().min(2, 'Enter a destination'), lat: z.number(), lon: z.number() }).refine((v) => v.lat !== 0 || v.lon !== 0, 'Select a destination suggestion'),
  departureLocal: z.string().min(1, 'Choose a departure time'), loadWeight: z.coerce.number().gt(0).lte(100000, 'Load must be at most 100,000 lb'),
  interval: z.coerce.number().refine((v): v is 10 | 25 | 50 => [10, 25, 50].includes(v), 'Choose 10, 25, or 50 miles'),
})
export type TripFormValues = z.infer<typeof tripSchema>
