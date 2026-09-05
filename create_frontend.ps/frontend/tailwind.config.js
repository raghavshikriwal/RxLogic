/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      obsidian: '#000000',
      paper: '#ffffff',
      charcoal: '#2f2f2f',
      ash: '#898989',
      fog: '#dddddd',
      slate: '#999999',
    },
    fontFamily: {
      clarkson: [
        'Clarkson',
        'ui-sans-serif',
        'system-ui',
        '-apple-system',
        'BlinkMacSystemFont',
        '"Segoe UI"',
        'Roboto',
        'sans-serif',
      ],
      serif: [
        'Clarkson Serif',
        'ui-serif',
        'Georgia',
        'Cambria',
        '"Times New Roman"',
        'Times',
        'serif',
      ],
    },
    fontSize: {
      caption: ['12px', { lineHeight: '1.4', letterSpacing: '-0.001em' }],
      'body-sm': ['14px', { lineHeight: '1.4', letterSpacing: '-0.01em' }],
      base: ['15px', { lineHeight: '1.4', letterSpacing: '-0.01em' }],
      subheading: ['20px', { lineHeight: '1.2', letterSpacing: '-0.02em' }],
      'heading-sm': ['26px', { lineHeight: '1.2', letterSpacing: '-0.04em' }],
      heading: ['40px', { lineHeight: '1', letterSpacing: '-0.05em' }],
      display: ['72px', { lineHeight: '0.93', letterSpacing: '-0.06em' }],
    },
    spacing: {
      0: '0px',
      8: '8px',
      16: '16px',
      24: '24px',
      32: '32px',
      40: '40px',
      48: '48px',
      56: '56px',
      80: '80px',
      120: '120px',
      240: '240px',
    },
    borderRadius: {
      none: '0px',
      sm: '3px',
      lg: '8px',
      '3xl': '30px',
      full: '100px',
    },
    extend: {
      maxWidth: {
        page: '1200px',
      },
      transitionTimingFunction: {
        editorial: 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        fadeUp: 'fadeUp 0.6s ease-out',
      },
    },
  },
  plugins: [],
};