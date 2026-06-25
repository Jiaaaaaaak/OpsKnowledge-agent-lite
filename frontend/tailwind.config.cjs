/** @type {import('tailwindcss').Config} */
// package.json 為 "type": "module"，故 .cjs 檔須用 CommonJS 匯出（與 postcss.config.cjs 一致），
// 不能用 ESM export default，否則 build 期會出現模組格式警告。
module.exports = {
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