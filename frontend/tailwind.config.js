/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
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
