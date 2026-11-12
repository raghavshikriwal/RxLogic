/** @type {import('tailwindcss').Config} */

/*
  RxLogic design system — Apple-inspired, light theme.
  Source of truth: DESIGN.md / tokens.json. Chromatic colour is reserved for
  interaction (blue) and clinical status (ember / critical / safe).

  Legacy aliases (obsidian, charcoal, ash, fog, slate, clarkson) are kept so
  components not yet migrated keep rendering. Remove them once every
  component uses the semantic names.
*/
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',

      // Neutrals
      ink: '#1d1d1f',
      'deep-gray': '#474747',
      'mid-gray': '#707070',
      'quiet-dot': '#777779',
      hairline: '#d6d6d6',
      'cool-wash': '#e8e8ed',
      canvas: '#f5f5f7',
      'faded-surface': '#fafafc',
      paper: '#ffffff',

      // RxLogic semantic brand palette
      'deep-navy': '#14263d',
      'intelligent-teal': '#087f8c',
      'soft-ivory': '#f7f8f6',
      'pale-blue': '#eaf1f5',
      'slate-gray': '#667587',

      // Accessible status colours (never communicate status by colour alone)
      'status-success': '#16845b',
      'status-warning': '#b7791f',
      'status-danger': '#c13d45',
      'status-info': '#3478b9',

      // Interaction (legacy blue retained for existing components)
      'electric-blue': '#0071e3',
      'blue-hover': '#0077ed',
      'blue-press': '#0067cc',
      'link-blue': '#0066cc',

      // Clinical status
      ember: '#b64400',
      'ember-wash': '#fdf1e7',
      critical: '#d70015',
      'critical-wash': '#fff0f1',
      safe: '#248a3d',
      'safe-wash': '#eef8f0',

      // Finish swatches (decorative surfaces)
      sky: '#c8d8e0',
      citrus: '#dddc8c',
      starlight: '#f0e4d3',
      silver: '#e3e4e5',
      blush: '#e8d0d0',
      indigo: '#596680',
      midnight: '#2e3642',

      // Legacy aliases
      obsidian: '#1d1d1f',
      charcoal: '#474747',
      ash: '#707070',
      fog: '#d6d6d6',
      slate: '#777779',
    },
    fontFamily: {
      display: [
        'Manrope',
        '"SF Pro Display"',
        'Inter',
        'ui-sans-serif',
        'system-ui',
        '-apple-system',
        'BlinkMacSystemFont',
        '"Segoe UI"',
        'Roboto',
        'sans-serif',
      ],
      sans: [
        'Inter',
        '"SF Pro Text"',
        'Inter',
        'ui-sans-serif',
        'system-ui',
        '-apple-system',
        'BlinkMacSystemFont',
        '"Segoe UI"',
        'Roboto',
        'sans-serif',
      ],
      // Legacy alias for unmigrated components.
      clarkson: [
        '"SF Pro Text"',
        'Inter',
        'ui-sans-serif',
        'system-ui',
        '-apple-system',
        'sans-serif',
      ],
      mono: ['"SF Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
    },
    fontSize: {
      micro: ['12px', { lineHeight: '16px', letterSpacing: '-0.01em' }],
      caption: ['14px', { lineHeight: '18px', letterSpacing: '-0.016em' }],
      'body-sm': ['17px', { lineHeight: '25px', letterSpacing: '-0.022em' }],
      base: ['17px', { lineHeight: '25px', letterSpacing: '-0.022em' }],
      body: ['21px', { lineHeight: '29px', letterSpacing: '0.011em' }],
      'body-lg': ['28px', { lineHeight: '32px', letterSpacing: '0.007em' }],
      subheading: ['32px', { lineHeight: '36px', letterSpacing: '0.004em' }],
      'heading-sm': ['40px', { lineHeight: '48px', letterSpacing: '-0.003em' }],
      heading: ['56px', { lineHeight: '60px', letterSpacing: '-0.005em' }],
      'heading-lg': ['80px', { lineHeight: '84px', letterSpacing: '-0.015em' }],
      display: ['96px', { lineHeight: '100px', letterSpacing: '-0.015em' }],
    },
    spacing: {
      0: '0px',
      4: '4px',
      8: '8px',
      12: '12px',
      16: '16px',
      20: '20px',
      24: '24px',
      28: '28px',
      32: '32px',
      40: '40px',
      44: '44px',
      48: '48px',
      52: '52px',
      56: '56px',
      76: '76px',
      80: '80px',
      120: '120px',
      144: '144px',
      240: '240px',
    },
    borderRadius: {
      none: '0px',
      sm: '3px',
      lg: '10px',
      '3xl': '28px',
      card: '28px',
      badge: '36px',
      pill: '980px',
      full: '9999px',
    },
    extend: {
      boxShadow: {
        'soft-card': '0 8px 30px rgba(20, 38, 61, 0.06)',
        'soft-popover': '0 18px 50px rgba(20, 38, 61, 0.12)',
      },
      maxWidth: { page: '1200px' },
      height: { nav: '48px' },
      transitionTimingFunction: {
        apple: 'cubic-bezier(0.28, 0.11, 0.32, 1)',
        'apple-out': 'cubic-bezier(0.16, 1, 0.3, 1)',
        editorial: 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
      transitionDuration: { 400: '400ms', 600: '600ms', 800: '800ms' },
      keyframes: {
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.96)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
      },
      animation: {
        fadeUp: 'fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) backwards',
        fadeIn: 'fadeIn 0.6s cubic-bezier(0.28, 0.11, 0.32, 1) backwards',
        scaleIn: 'scaleIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) backwards',
      },
    },
  },
  plugins: [],
};
