import type { Config } from 'tailwindcss'

export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        risk: {
          low: '#2e9e5b',
          moderate: '#f2c230',
          high: '#f28c28',
          severe: '#d93636',
          noTravel: '#3b0a45',
          unknown: '#9ca3af',
        },
        route: {
          a: '#1f77b4',
          b: '#7b4fd6',
          c: '#00a6a6',
        },
      },
    },
  },
  plugins: [],
} satisfies Config
