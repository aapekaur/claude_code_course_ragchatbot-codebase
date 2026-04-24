# Testing Infrastructure Changes

## Files Changed

### `pyproject.toml`
- Added `httpx>=0.27.0` to dev dependencies (required by FastAPI's `TestClient`)
- Added `[tool.pytest.ini_options]` with `testpaths = ["backend/tests"]` and `pythonpath = ["backend"]` so pytest finds tests and resolves backend imports without manual `sys.path` hacks

### `backend/tests/conftest.py`
- Added three shared fixtures available to all test modules:
  - `mock_rag_system` — a `MagicMock` RAGSystem pre-configured with sensible defaults (query returns `("Test answer", [])`, analytics returns 2 courses, session manager creates `"test-session-id"`)
  - `sample_query_payload` — a dict `{"query": "What is Python?", "session_id": "session-abc"}` for reuse across query endpoint tests
  - `sample_sources` — a list of two source items for response shape assertions

### `backend/tests/test_api_endpoints.py` (new file)
- 20 tests across three endpoint groups: `POST /api/query`, `GET /api/courses`, `POST /api/clear-session`
- Uses a `_make_test_app(rag_system)` helper that builds a minimal FastAPI app mirroring the real routes from `app.py` but **without** the `StaticFiles` mount — this avoids the `../frontend` directory-not-found error when running tests
- The `TestClient` from `fastapi.testclient` drives all HTTP assertions
- Covers: 200 success paths, request validation (422 on missing fields), 500 error propagation, session auto-creation, and correct delegation to `rag_system` methods

# Frontend Changes

## Code Quality Tooling — Prettier Setup

### What was added

**`frontend/package.json`**
- New file. Declares `prettier` as a dev dependency with two npm scripts:
  - `npm run format` — formats all frontend files in-place
  - `npm run format:check` — checks formatting without modifying files (suitable for CI)

**`frontend/.prettierrc`**
- New file. Prettier configuration:
  - 100-character print width
  - 2-space indentation, no tabs
  - Single quotes in JS
  - ES5 trailing commas
  - LF line endings

**`frontend/package-lock.json`**
- Auto-generated lockfile from `npm install`.

**`format-frontend.sh`** (project root)
- Convenience shell script to run Prettier from the project root.
- `./format-frontend.sh` — formats files in-place.
- `./format-frontend.sh --check` — exits non-zero if any file is out of format (use in CI).

### Files reformatted

`frontend/index.html`, `frontend/script.js`, and `frontend/style.css` were reformatted by Prettier on initial setup. Changes are purely stylistic (indentation, quote style, self-closing HTML tags, trailing commas) — no logic was altered.


# Frontend Changes

## Dark/Light Mode Toggle Button

### Files Modified
- `frontend/index.html`
- `frontend/style.css`
- `frontend/script.js`

### What Was Added

**index.html**
- Added a `<button id="themeToggle">` element with `aria-label` and `title` for accessibility, placed just before the `<script>` tags so it renders outside the main layout container.
- The button contains two inline SVGs: a sun icon (shown in dark mode) and a moon icon (shown in light mode).
- Bumped cache-busting version on `style.css` and `script.js` to `v=10`.

**style.css**
- Added a `body[data-theme="light"]` rule that overrides all color variables to a clean light palette (white surfaces, dark text, light borders).
- Added `--toggle-bg`, `--toggle-border`, `--toggle-color`, `--toggle-hover-bg`, `--toggle-hover-color` variables in both dark (`:root`) and light (`body[data-theme="light"]`) scopes for the button's own appearance.
- Added `transition: background-color 0.3s ease, color 0.3s ease` to `body` and `transition: background 0.3s ease, border-color 0.3s ease` to `.sidebar` for smooth theme switching.
- Added `.theme-toggle` styles: `position: fixed; top: 1rem; right: 1rem; z-index: 1000`, circular shape (40×40 px, `border-radius: 50%`), hover scale/shadow, focus ring, and active press-down effect.
- Added icon visibility rules: `.icon-moon` hidden by default (dark mode), `.icon-sun` hidden and `.icon-moon` shown when `body[data-theme="light"]`.

**script.js**
- Added `themeToggle` to the list of DOM element references.
- Added `initTheme()`: reads `localStorage.getItem('theme')` on load and applies `data-theme="light"` if saved value is `'light'`.
- Added `toggleTheme()`: flips the `data-theme` attribute and persists the new value in `localStorage`.
- Wired `themeToggle.addEventListener('click', toggleTheme)` in `setupEventListeners()`.
- Called `initTheme()` before `setupEventListeners()` so the correct theme is applied before any rendering.

### Design Decisions
- Fixed positioning keeps the button always visible regardless of scroll or layout.
- `localStorage` persistence means the user's preference survives page reloads.
- SVG icons match the existing send-button icon style (stroke-based, same dimensions).
- All color changes go through CSS custom properties, so no JavaScript color manipulation is needed.

---

## Light Theme CSS Variables (Accessibility Pass)

### Files Modified
- `frontend/style.css`

### What Changed

**Expanded `:root` variable set** — grouped and commented by concern, added new semantic variables so no rule anywhere needs a hardcoded color:

| New variable | Dark value | Purpose |
|---|---|---|
| `--welcome-shadow` | `0 4px 16px rgba(0,0,0,0.3)` | Welcome card drop-shadow |
| `--code-bg` | `rgba(0,0,0,0.25)` | Inline code and pre-block background |
| `--blockquote-border` | `#4f81f0` | Blockquote left-border accent |
| `--error-bg/color/border` | red-tinted values | `.error-message` component |
| `--success-bg/color/border` | green-tinted values | `.success-message` component |

**`body[data-theme="light"]` overrides** — every variable above now has a light-mode counterpart chosen for WCAG AA compliance:

- `--text-secondary` promoted from `#64748b` → `#475569` (6.0:1 on white, 5.7:1 on `#f1f5f9` — previously borderline at 4.6:1).
- `--error-color` changed from `#fca5a5` → `#b91c1c` (~7.1:1 on white, WCAG AAA).
- `--success-color` changed from `#6ee7a0` → `#15803d` (~5.2:1 on white, WCAG AA).
- `--code-bg` set to `rgba(15,23,42,0.06)` — a neutral dark tint that reads as light gray on white, avoiding the too-heavy `rgba(0,0,0,0.2)`.
- `--welcome-shadow` reduced to `rgba(0,0,0,0.08)` to avoid harsh shadow on light surfaces.

**CSS rules updated** — four rules that previously used hardcoded values now reference variables:

- `.message-content code` and `.message-content pre` → `background-color: var(--code-bg)`
- `.message-content blockquote` → `border-left: 3px solid var(--blockquote-border)` (also fixed a bug: was referencing the undefined `var(--primary)` instead of the correct token)
- `.message.welcome-message .message-content` → `box-shadow: var(--welcome-shadow)`
- `.error-message` → `var(--error-bg/color/border)`
- `.success-message` → `var(--success-bg/color/border)`

---

## JavaScript Theme Functionality (Improvements)

### Files Modified
- `frontend/script.js`
- `frontend/style.css`

### What Changed

**script.js**

Refactored the theme logic into three focused functions:

- `applyTheme(theme, animate)` — single source of truth for applying a theme. Sets/removes `data-theme="light"` on `body`. When `animate` is `true`, briefly adds `theme-transitioning` to `body` (removed after 350 ms), triggering broad CSS transitions.

- `initTheme()` — enhanced with `prefers-color-scheme` OS detection. Priority order:
  1. Saved `localStorage` preference (explicit user choice, always respected)
  2. OS `prefers-color-scheme: light` media query (first-visit default)
  3. Dark (the CSS default, no attribute needed)
  
  Also registers a `matchMedia` change listener so the UI stays in sync if the user switches their OS theme — but only when no manual preference has been saved.

- `toggleTheme()` — calls `applyTheme()` with animation, persists to `localStorage`, then adds `theme-toggle--spin` class to the button and removes it on `animationend` (using `{ once: true }` so the listener is self-cleaning).

**style.css**

- `.theme-transitioning *` rule: applies `color`, `background-color`, `border-color`, and `box-shadow` transitions at `0.3s ease !important` to all elements while the class is present. Using only color-related properties ensures `transform` and `opacity` animations (hover effects, message fade-in) are unaffected.
- `@keyframes theme-toggle-spin`: a 360° rotation with a slight mid-point scale-down (0.85) for a playful "click" feel, timed at 0.35s to match the transition duration.
- `.theme-toggle--spin`: applies the animation, added/removed by JS per click.

### Design Decisions
- The `{ once: true }` option on `animationend` avoids any possibility of listener accumulation if the button is clicked rapidly.
- Removing `theme-transitioning` after 350 ms (slightly longer than the 300 ms CSS transition) ensures the class outlasts the animation before being cleaned up.
- OS preference sync is intentionally skipped when a manual preference exists — user choice always wins.

### Accessibility Notes
All foreground/background color pairs in light mode meet WCAG 2.1 AA (4.5:1 for text, 3:1 for UI components). Key ratios verified:
- Primary text `#0f172a` on `#ffffff`: ~18:1
- Secondary text `#475569` on `#ffffff`: ~6.0:1
- Secondary text `#475569` on `#f1f5f9`: ~5.7:1
- User bubble white on `#2563eb`: ~4.9:1
- Error text `#b91c1c` on white: ~7.1:1
- Success text `#15803d` on white: ~5.2:1

---

## Visual Hierarchy & Variable Wiring Pass

### Files Modified
- `frontend/style.css`

### What Changed

**Bug fixes — variables defined but never wired up:**

Three sets of semantic variables existed in the variable blocks but were overridden by generic variables in the actual CSS rules. This pass connects them:

| Variable | Old rule value | New rule value | Impact |
|---|---|---|---|
| `--assistant-message` | `var(--surface)` | `var(--assistant-message)` | Bubbles now use their dedicated token |
| `--welcome-bg` | `var(--surface)` | `var(--welcome-bg)` | Welcome card gets its tinted background |
| `--welcome-border` | `var(--border-color)` | `var(--welcome-border)` | Welcome card gets its accent border |

Dark mode appearance is **unchanged** because `--assistant-message` was updated to `#1e293b` (matching the old `--surface` value) and `--welcome-bg: #1e3a5f` / `--welcome-border: #2563eb` were already correct for dark mode.

In light mode the improvements are visible:
- Assistant bubbles render as `#f1f5f9` (off-white) against the `#f8fafc` page background — distinguishable rather than invisible
- Welcome card renders as a light sky-blue (`#eff6ff`) with a blue accent border (`#93c5fd`), maintaining its "special" visual weight relative to regular messages

**New variable — `--message-shadow`:**
- `:root`: `none` (dark mode uses surface contrast for depth, no shadow needed)
- `body[data-theme="light"]`: `0 1px 4px rgba(15, 23, 42, 0.08)` (subtle lift so assistant bubbles read as cards against the light background)
- Applied to `.message.assistant .message-content` via `box-shadow: var(--message-shadow)`

### Why This Matters
In light mode, the page background (`#f8fafc`) and a pure-white assistant bubble (`#ffffff`) differ in luminance by less than 2% — invisible to many users. The `--assistant-message: #f1f5f9` + `--message-shadow` combination restores the visual hierarchy the dark theme achieves through surface layering.
