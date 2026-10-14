/** @type {import('tailwindcss').Config} */
const colors = require('tailwindcss/colors')

module.exports = {
  content: ['./templates/*.html', './templates/**/*.html',
            './templates/**/**/*.html',
            './apps/indexer/templates/indexer/*.html',
            './apps/indexer/templates/indexer/bits/*.html',
            './apps/select/templates/select/*.html',
            './static/js/select_cache.js',
            './static/js/select_search_panels.js',
	    './apps/voting/templates/voting/*.html',
            './apps/gcd/markdown_extension.py',],
  theme: {
  extend: {
      colors: {
        normal: "#0a0a0a",
        'normal-gcd': "#0a0a0a",
        'gcd': '#66E',
        'link-gcd': '#2727eb',
        'index-status-edit': '#E77',
        'index-status-in-queue': '#EA7',
        'my-comics': '#A9302A',
        'preview': '#FFE944',
        'visited-gcd': '#551A8B',
      },
      screens: {
        'xs': '480px',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}
