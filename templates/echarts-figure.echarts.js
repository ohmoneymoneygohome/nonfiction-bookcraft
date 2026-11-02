// Replace DATA with verified values from the registered data file.
// Keep the source note in FIGURE_REGISTER.json and in the final figure caption.
const option = {
  animation: false,
  title: { text: 'Figure title' },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: ['2024', '2025', '2026'] },
  yAxis: { type: 'value', name: 'Unit' },
  series: [{ type: 'line', data: [/* DATA */] }]
};

// Render this option to SVG/PNG for the PDF after checking the source and unit.
