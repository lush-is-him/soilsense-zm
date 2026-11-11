// Animated step illustrations for the guided soil test (inline SVG with SMIL
// animation: no images or libraries, so they load instantly on a phone).
"use strict";

const ANIM = {
  // 1. Walk the field in a zig-zag and take 15-20 small samples.
  sample: `<svg viewBox="0 0 320 200" class="anim" role="img" aria-label="Walking across the field in a zig-zag, taking a small sample at each stop">
    <rect x="10" y="10" width="300" height="180" rx="14" fill="#9cc58a"/>
    <g stroke="#7fae6c" stroke-width="3">${[30, 60, 90, 120, 150, 180].map((y) => `<line x1="20" y1="${y}" x2="300" y2="${y}"/>`).join("")}</g>
    <path id="zig" d="M30 30 L110 170 L170 30 L230 170 L290 30" fill="none" stroke="#5b3a1a" stroke-width="3" stroke-dasharray="8 8">
      <animate attributeName="stroke-dashoffset" from="160" to="0" dur="4s" repeatCount="indefinite"/></path>
    ${[[30, 30], [70, 100], [110, 170], [140, 100], [170, 30], [200, 100], [230, 170], [260, 100], [290, 30]].map(([x, y], i) => `
      <circle cx="${x}" cy="${y}" r="7" fill="#5b3a1a" opacity="0">
        <animate attributeName="opacity" values="0;0;1;1" keyTimes="0;${(i / 9).toFixed(2)};${((i + 0.5) / 9).toFixed(2)};1" dur="6s" repeatCount="indefinite"/></circle>`).join("")}
    <g><circle r="11" fill="#f2c14e" stroke="#7a5a00" stroke-width="2"/><text y="5" text-anchor="middle" font-size="13" font-weight="700" fill="#3b2a00">✋</text>
      <animateMotion dur="6s" repeatCount="indefinite" path="M30 30 L110 170 L170 30 L230 170 L290 30"/></g>
  </svg>`,

  // 2. Dig to 20 cm at each spot, put the soil in one clean bucket, mix.
  bucket: `<svg viewBox="0 0 320 200" class="anim" role="img" aria-label="Soil from 0 to 20 cm is dug at each spot and mixed in one bucket">
    <rect x="0" y="60" width="150" height="140" fill="#8a5a33"/><rect x="0" y="60" width="150" height="10" fill="#6f9d55"/>
    <g font-size="12" fill="#fff"><line x1="130" y1="70" x2="130" y2="170" stroke="#fff" stroke-width="2"/>
      <text x="100" y="78">0 cm</text><text x="92" y="172">20 cm</text></g>
    <g><rect x="40" y="10" width="14" height="70" fill="#9aa3a8"/><path d="M30 80 h34 l-8 34 h-18z" fill="#c7ced2"/>
      <animateTransform attributeName="transform" type="translate" values="0 0; 0 70; 0 70; 0 0" keyTimes="0;0.4;0.6;1" dur="3s" repeatCount="indefinite"/></g>
    <path d="M200 90 h90 l-12 100 h-66z" fill="#d8dde0" stroke="#7d868c" stroke-width="3"/>
    <ellipse cx="245" cy="90" rx="45" ry="9" fill="#bfc6ca" stroke="#7d868c" stroke-width="3"/>
    ${[0, 1, 2].map((i) => `<circle cx="${225 + i * 18}" cy="40" r="7" fill="#7a4b26">
      <animate attributeName="cy" values="30;120" dur="1.5s" begin="${i * 0.5}s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="1;1;0" keyTimes="0;0.8;1" dur="1.5s" begin="${i * 0.5}s" repeatCount="indefinite"/></circle>`).join("")}
    <rect x="215" y="140" width="60" height="40" rx="6" fill="#7a4b26"/>
  </svg>`,

  // 3. Dry in the shade, crush and sieve.
  sieve: `<svg viewBox="0 0 320 200" class="anim" role="img" aria-label="The soil is dried, crushed and shaken through a sieve">
    <circle cx="50" cy="45" r="22" fill="#f2c14e"><animate attributeName="r" values="20;24;20" dur="2s" repeatCount="indefinite"/></circle>
    <rect x="15" y="150" width="120" height="16" rx="8" fill="#b08355"/><text x="20" y="190" font-size="13" fill="#4a5248">dry 2–3 days</text>
    <g><ellipse cx="225" cy="70" rx="70" ry="14" fill="none" stroke="#5c646a" stroke-width="4"/>
      <path d="M155 70 l10 25 h120 l10 -25" fill="none" stroke="#5c646a" stroke-width="4"/>
      <path d="M165 95 h120" stroke="#5c646a" stroke-width="2" stroke-dasharray="3 3"/>
      <ellipse cx="225" cy="66" rx="45" ry="7" fill="#8a5a33"/>
      <animateTransform attributeName="transform" type="translate" values="-6 0;6 0;-6 0" dur="0.5s" repeatCount="indefinite"/></g>
    ${[0, 1, 2, 3, 4, 5].map((i) => `<circle cx="${190 + i * 14}" cy="100" r="2.5" fill="#7a4b26">
      <animate attributeName="cy" values="100;175" dur="1.2s" begin="${(i * 0.2).toFixed(1)}s" repeatCount="indefinite"/></circle>`).join("")}
    <path d="M180 175 h90 l-8 18 h-74z" fill="#7a4b26"/>
  </svg>`,

  // 4. 10 ml soil, 30 ml clean water, stir, wait.
  cup: `<svg viewBox="0 0 320 200" class="anim" role="img" aria-label="10 millilitres of soil and 30 millilitres of water are put in a cup and stirred">
    <defs><clipPath id="cupclip"><path d="M110 40 h100 l-12 140 h-76z"/></clipPath></defs>
    <g clip-path="url(#cupclip)">
      <rect x="100" y="180" width="120" height="0" fill="#7a4b26"><animate attributeName="y" values="180;150;150" keyTimes="0;0.3;1" dur="6s" repeatCount="indefinite"/>
        <animate attributeName="height" values="0;30;30" keyTimes="0;0.3;1" dur="6s" repeatCount="indefinite"/></rect>
      <rect x="100" y="150" width="120" height="0" fill="#7fb6d6" opacity="0.75"><animate attributeName="y" values="150;150;60;60" keyTimes="0;0.35;0.7;1" dur="6s" repeatCount="indefinite"/>
        <animate attributeName="height" values="0;0;90;90" keyTimes="0;0.35;0.7;1" dur="6s" repeatCount="indefinite"/></rect>
    </g>
    <path d="M110 40 h100 l-12 140 h-76z" fill="none" stroke="#5c646a" stroke-width="4"/>
    <g font-size="12" fill="#4a5248"><line x1="214" y1="150" x2="226" y2="150" stroke="#4a5248"/><text x="230" y="154">10 ml soil</text>
      <line x1="210" y1="60" x2="222" y2="60" stroke="#4a5248"/><text x="226" y="64">+ 30 ml water</text></g>
    <g><rect x="158" y="10" width="6" height="120" rx="3" fill="#9aa3a8"/>
      <animateTransform attributeName="transform" type="rotate" values="-12 161 130;12 161 130;-12 161 130" dur="1s" begin="4.2s" repeatCount="indefinite"/></g>
    <text x="20" y="190" font-size="13" fill="#4a5248">stir, wait 10 min, stir again</text>
  </svg>`,

  // 5. Put the probe in; the pH appears on the screen.
  probe: `<svg viewBox="0 0 320 200" class="anim" role="img" aria-label="The probe goes into the cup and the pH appears on the phone">
    <path d="M60 80 h90 l-10 110 h-70z" fill="#a8c9dc" stroke="#5c646a" stroke-width="4"/>
    <rect x="68" y="160" width="74" height="28" fill="#7a4b26" opacity="0.8"/>
    <g><rect x="98" y="0" width="14" height="110" rx="6" fill="#e9eef1" stroke="#5c646a" stroke-width="3"/>
      <circle cx="105" cy="112" r="9" fill="#d8eef6" stroke="#5c646a" stroke-width="3"/>
      <animateTransform attributeName="transform" type="translate" values="0 -40;0 40;0 40" keyTimes="0;0.4;1" dur="4s" repeatCount="indefinite"/></g>
    <rect x="190" y="40" width="100" height="150" rx="14" fill="#1f2a24"/><rect x="200" y="55" width="80" height="115" rx="6" fill="#f6f3ea"/>
    <text x="240" y="100" text-anchor="middle" font-size="14" fill="#4a5248">pH</text>
    <text x="240" y="132" text-anchor="middle" font-size="26" font-weight="700" fill="#198754" opacity="0">6.9
      <animate attributeName="opacity" values="0;0;1;1" keyTimes="0;0.55;0.7;1" dur="4s" repeatCount="indefinite"/></text>
  </svg>`,

  // Calibration: pH 7 buffer, rinse, pH 4 buffer.
  calibrate: `<svg viewBox="0 0 320 200" class="anim" role="img" aria-label="Probe in pH 7 buffer, rinse, then pH 4 buffer">
    <g font-size="14" font-weight="700" text-anchor="middle">
      <path d="M20 90 h70 l-8 90 h-54z" fill="#c9e7c9" stroke="#5c646a" stroke-width="3"/><text x="55" y="150" fill="#1f5e2c">pH 7</text>
      <path d="M125 90 h70 l-8 90 h-54z" fill="#e8f1f6" stroke="#5c646a" stroke-width="3"/><text x="160" y="150" fill="#2f5f8a">water</text>
      <path d="M230 90 h70 l-8 90 h-54z" fill="#f6d7c3" stroke="#5c646a" stroke-width="3"/><text x="265" y="150" fill="#8a3d12">pH 4</text></g>
    <g><rect x="-7" y="0" width="14" height="95" rx="6" fill="#e9eef1" stroke="#5c646a" stroke-width="3"/>
      <animateTransform attributeName="transform" type="translate" values="55 -10;55 30;55 30;55 -10;160 -10;160 30;160 -10;265 -10;265 30;265 30;55 -10"
        keyTimes="0;0.1;0.3;0.35;0.45;0.5;0.6;0.7;0.75;0.95;1" dur="8s" repeatCount="indefinite"/></g>
  </svg>`,
};
