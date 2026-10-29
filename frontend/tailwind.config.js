/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Acento verde petróleo (task pack §5 "Diseño visual").
        petrol: {
          50: '#eef6f7',
          100: '#d5e9ec',
          200: '#acd2d8',
          300: '#7bb3bd',
          400: '#4a8f9c',
          500: '#2a7080',
          600: '#1a5a69',
          700: '#0f4c5c',
          800: '#0c3d4a',
          900: '#0a2f39',
          950: '#061d24',
        },
        canvas: '#f4f6f6',
      },
      fontFamily: {
        sans: ['"Public Sans"', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
