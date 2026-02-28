/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: 'var(--brand-primary)',
          dark: 'var(--brand-primary-dark)',
          light: 'var(--brand-primary-light)',
          surface: 'var(--brand-surface)',
          'surface-dark': 'var(--brand-surface-dark)',
          border: 'var(--brand-border)',
        },
        surface: {
          DEFAULT: 'var(--surface-primary)',
          secondary: 'var(--surface-secondary)',
          tertiary: 'var(--surface-tertiary)',
          elevated: 'var(--surface-elevated)',
          card: 'var(--surface-card)',
          'card-hover': 'var(--surface-card-hover)',
        },
        accent: {
          success: {
            DEFAULT: 'var(--accent-success)',
            light: 'var(--accent-success-light)',
            muted: 'var(--accent-success-muted)',
            dark: 'var(--accent-success-dark)',
          },
          danger: {
            DEFAULT: 'var(--accent-danger)',
            light: 'var(--accent-danger-light)',
            muted: 'var(--accent-danger-muted)',
            dark: 'var(--accent-danger-dark)',
          },
          warning: {
            DEFAULT: 'var(--accent-warning)',
            light: 'var(--accent-warning-light)',
            muted: 'var(--accent-warning-muted)',
            dark: 'var(--accent-warning-dark)',
          },
          info: {
            DEFAULT: 'var(--accent-info)',
            light: 'var(--accent-info-light)',
            muted: 'var(--accent-info-muted)',
            dark: 'var(--accent-info-dark)',
          },
        },
        chart: {
          sma50: 'var(--chart-sma50)',
        },
      },
      textColor: {
        primary: 'var(--text-primary)',
        secondary: 'var(--text-secondary)',
        tertiary: 'var(--text-tertiary)',
        muted: 'var(--text-muted)',
      },
      borderColor: {
        DEFAULT: 'var(--border-light)',
        medium: 'var(--border-medium)',
        heavy: 'var(--border-dark)',
      },
      divideColor: {
        DEFAULT: 'var(--border-light)',
        medium: 'var(--border-medium)',
      },
      ringColor: {
        DEFAULT: 'var(--brand-primary)',
        brand: 'var(--brand-primary)',
      },
    },
  },
  plugins: [],
}
