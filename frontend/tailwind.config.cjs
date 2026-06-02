/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#f8fafc',
        card: '#ffffff',
        primary: '#4f46e5', // indigo-600
        secondary: '#64748b', // slate-500
        success: '#10b981', // emerald-500
        warning: '#f59e0b', // amber-500
        error: '#ef4444', // red-500
        inactive: '#94a3b8', // slate-400
      }
    },
  },
  plugins: [],
}