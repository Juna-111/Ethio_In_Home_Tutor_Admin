/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: '#172924',
        pine: '#183b34',
        paper: '#fbfcf9',
        coral: '#c35d47',
        citrus: '#a88221',
        muted: '#78847c',
        line: '#e2e7df',
        green: {
          DEFAULT: '#27715e',
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
        },
        telegram: {
          blue: '#2481cc',
          'blue-dark': '#1c66a3',
          bg: '#ffffff',
          'secondary-bg': '#f4f4f5',
          text: '#000000',
          hint: '#999999'
        }
      }
    },
  },
  plugins: [],
}
