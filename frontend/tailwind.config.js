/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      colors: {
        brand: {
          50:  '#f3f7fb',
          100: '#e7eef8',
          200: '#d4dfef',
          300: '#b8c9e3',
          400: '#8aa7d1',
          500: '#5d7eb8',
          600: '#4769a1',
          700: '#355385',
          800: '#29456d',
          900: '#1d2f4d',
        },
      },
      boxShadow: {
        soft: '0 12px 32px -16px rgba(15, 23, 42, 0.22)',
      },
    },
  },
  plugins: [],
}
