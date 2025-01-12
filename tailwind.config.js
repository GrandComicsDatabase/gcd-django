/** @type {import('tailwindcss').Config} */
const colors = require('tailwindcss/colors')
module.exports = {
  content: ['./templates/*.html', './templates/**/*.html', './templates/**/**/*.html'],
  theme: {
  extend: {
      colors: {
        normal: "neutral-950",
        'normal-gcd': "neutral-950",
        'gcd': '#66E',
        'link-gcd': '#2727eb',
        'visited-gcd': 'purple-800',
      },
    },
  },
}

