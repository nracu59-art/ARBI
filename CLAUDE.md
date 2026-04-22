# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ARBI (Asset Recovery Bureau of Investigation) is a static single-page application presenting Moldova's anti-corruption agency's 2025 Annual Activity Report. All content is in Romanian. The entire application lives in a single file: `ARBI 2025.html`.

## Running the Project

No build step required. Open `ARBI 2025.html` directly in any modern browser. There are no dependencies to install, no package manager, and no local server needed.

## Architecture

The application is a self-contained HTML file (~30KB) with three embedded layers:

- **CSS** (lines 9–35): Tailwind CSS loaded via CDN, with minimal custom overrides.
- **HTML** (lines 37–358): Sidebar navigation + main content area. Each module is a `<div>` section toggled by the JS state.
- **JavaScript** (lines 360–445): Vanilla ES6+. A global `state` object tracks the active module and caches Chart.js instances to avoid re-rendering.

External CDN dependencies: Tailwind CSS, Chart.js, Google Fonts (Plus Jakarta Sans).

## Navigation & Module System

`switchModule(moduleId)` is the core function — it hides all sections, shows the selected one, and triggers lazy chart rendering on first visit. Charts are cached in `state.charts` after first render to avoid flickering on tab revisit.

The six modules:
| ID | Content |
|----|---------|
| `home` | KPI dashboard (424 delegații, 674 subiecți, 307 cauze) |
| `modul1` | Financial investigations — bar chart (2023–2025 trends) |
| `modul2` | Asset seizures — doughnut chart (1.2B MDL total) |
| `modul3` | SIA RBII digital registry & ASP database integration |
| `modul4` | International cooperation (38 countries, CARIN/SIENA/INTERPOL) |
| `modul5` | 2026 strategic objectives (6 initiatives) |

## Key Patterns

- **Lazy chart rendering**: charts initialize only when their module is first activated, checked via `state.charts[id]`.
- **Image fallback**: `onerror` handlers on `<img>` tags replace broken external images with a placeholder.
- All data (metrics, chart values) is hardcoded — there is no backend or API.
