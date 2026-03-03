#!/usr/bin/env node
/**
 * Generates frontend/src/theme.css from shared/colors.json.
 *
 * Run after modifying shared/colors.json to keep the CSS variables in sync:
 *   node scripts/generate-theme.js
 *
 * The generated file is the runtime source of truth for all frontend colors.
 * shared/colors.json is the authoritative source — this script prevents drift.
 */

import { readFileSync, writeFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
const COLORS_PATH = resolve(ROOT, 'shared', 'colors.json');
const THEME_PATH = resolve(ROOT, 'frontend_v2', 'src', 'theme.css');

const colors = JSON.parse(readFileSync(COLORS_PATH, 'utf-8'));

function cssVar(prefix, key) {
  // Convert camelCase to kebab-case: primaryDark -> primary-dark
  const kebab = key.replace(/([A-Z])/g, '-$1').toLowerCase();
  return `--${prefix}-${kebab}`;
}

function emitSection(title, prefix, obj, indent = '  ') {
  const lines = [`\n${indent}/* ${title} */`];
  for (const [key, value] of Object.entries(obj)) {
    if (typeof value === 'string') {
      lines.push(`${indent}${cssVar(prefix, key)}: ${value};`);
    }
    // Skip nested objects (handled separately)
  }
  return lines.join('\n');
}

// Build the CSS output
let css = `/**
 * George Researcher Theme System
 *
 * AUTO-GENERATED from shared/colors.json — do not edit manually.
 * Run: node scripts/generate-theme.js
 *
 * All brand colors are defined here. To rebrand:
 * 1. Edit shared/colors.json
 * 2. Run this script
 * 3. That's it — the entire app will update
 *
 * Color naming convention:
 * - brand-*: Primary brand colors (amber/orange family)
 * - surface-*: Background colors
 * - text-*: Text colors
 * - accent-*: Semantic accent colors (success, danger, etc.)
 * - chart-*: Chart-specific colors
 */

:root {`;

// Brand colors
css += emitSection('BRAND COLORS — buttons, links, highlights', 'brand', colors.brand);

// Surface colors
css += emitSection('SURFACE COLORS — backgrounds', 'surface', colors.surface);

// Text colors
css += emitSection('TEXT COLORS', 'text', colors.text);

// Border colors
css += emitSection('BORDER COLORS', 'border', colors.border);

// Semantic accent colors
css += '\n\n  /* SEMANTIC ACCENT COLORS */';
const semanticMap = {
  success: ['success', 'successLight', 'successMuted', 'successDark'],
  danger: ['danger', 'dangerLight', 'dangerMuted', 'dangerDark'],
  warning: ['warning', 'warningLight', 'warningMuted', 'warningDark'],
  info: ['info', 'infoLight', 'infoMuted', 'infoDark'],
};
for (const [group, keys] of Object.entries(semanticMap)) {
  for (const key of keys) {
    const varName = cssVar('accent', key);
    css += `\n  ${varName}: ${colors.semantic[key]};`;
  }
}

// Chart colors
css += emitSection('CHART COLORS', 'chart', colors.chart);

// Badge colors
css += '\n\n  /* PRIORITY BADGES */';
for (const [level, vals] of Object.entries(colors.badges)) {
  css += `\n  --badge-${level}-bg: ${vals.bg};`;
  css += `\n  --badge-${level}-text: ${vals.text};`;
}

css += '\n}\n';

// Dark mode
css += `
/* ==========================================
 * DARK MODE
 * ========================================== */

html.dark {`;

const dm = colors.darkMode;
css += emitSection('Brand colors — brighter for dark backgrounds', 'brand', dm.brand);
css += emitSection('Surfaces', 'surface', dm.surface);
css += emitSection('Text', 'text', dm.text);
css += emitSection('Borders', 'border', dm.border);

// Dark mode semantic
css += '\n\n  /* Semantic accents (adjusted for dark) */';
for (const [group, keys] of Object.entries(semanticMap)) {
  for (const key of keys) {
    if (dm.semantic[key]) {
      css += `\n  ${cssVar('accent', key)}: ${dm.semantic[key]};`;
    }
  }
}

// Dark mode chart
css += emitSection('Charts', 'chart', dm.chart);

// Dark mode badges
css += '\n\n  /* Priority badges */';
for (const [level, vals] of Object.entries(dm.badges)) {
  css += `\n  --badge-${level}-bg: ${vals.bg};`;
  css += `\n  --badge-${level}-text: ${vals.text};`;
}

css += '\n}\n';

// Utility classes
css += `
/* ==========================================
 * UTILITY CLASSES
 * ========================================== */

/* Brand gradient background */
.bg-brand-gradient {
  background: linear-gradient(to right, var(--brand-gradient-from), var(--brand-gradient-to));
}

/* Brand surface (light amber background) */
.bg-brand-surface {
  background-color: var(--brand-surface);
}

/* Card section background */
.bg-surface-card {
  background-color: var(--surface-card);
}

/* Text on brand */
.text-brand {
  color: var(--brand-primary);
}

/* Priority badges */
.badge-high {
  background-color: var(--badge-high-bg);
  color: var(--badge-high-text);
}

.badge-medium {
  background-color: var(--badge-medium-bg);
  color: var(--badge-medium-text);
}

.badge-low {
  background-color: var(--badge-low-bg);
  color: var(--badge-low-text);
}

/* Belief badge (Analyst Notes) */
.belief-badge {
  background-color: var(--accent-warning-light);
  color: var(--accent-warning-dark);
}

/* Accent gradient utilities */
.bg-accent-success-gradient {
  background: linear-gradient(to right, var(--accent-success), var(--accent-success-dark));
}

.bg-accent-danger-gradient {
  background: linear-gradient(to right, var(--accent-danger), var(--accent-danger-dark));
}

.bg-accent-warning-gradient {
  background: linear-gradient(to right, var(--accent-warning), var(--accent-warning-dark));
}

.bg-accent-info-gradient {
  background: linear-gradient(to right, var(--accent-info), var(--accent-info-dark));
}
`;

writeFileSync(THEME_PATH, css, 'utf-8');
console.log(`Generated ${THEME_PATH} from ${COLORS_PATH}`);
