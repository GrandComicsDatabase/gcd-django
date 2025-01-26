/** @type {import('tailwindcss').Config} */
const colors = require('tailwindcss/colors')
module.exports = {
  content: ['./templates/*.html', './templates/**/*.html', './templates/**/**/*.html'],
  theme: {
  extend: {
      colors: {
        normal: "#0a0a0a",
        'normal-gcd': "#0a0a0a",
        'gcd': '#66E',
        'link-gcd': '#2727eb',
        'preview': '#FFE944',
        'visited-gcd': '#551A8B',
      },
    },
  },
}

