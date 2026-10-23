# Design System and UI Specification

## 1. Visual Direction & Philosophy

EatData is an engineering and analytics workbench, not a generic dashboard or decorative AI wrapper.

### Core Principles
- **Data Clarity Over Decoration**: Neutral, restrained surfaces that let data and quality metrics take center stage.
- **High Information Density**: Precise spacing, compact tables, and clear typographic hierarchy for efficient scanning.
- **Predictable Control**: Explicit states, interactive previews, and unmistakable feedback for destructive operations.
- **Accessible By Default**: High contrast ratios (WCAG AA minimum), readable monospace alignments for numeric data, and no status communicated by color alone.

---

## 2. Workspace Layout

The desktop interface is partitioned into clean, persistent functional zones:

1. **Workspace & Dataset Bar**:
   - Loaded dataset selector, file metadata (path, size, encoding, modified timestamp), row and column count pills.
   - Mode indicators (Offline / Local Model / Cloud AI).
2. **Dataset Profile & Schema View**:
   - Column grid with inferred data types, confidence scores, null percentages, distinct counts, and anomaly badges.
   - Column-level inspection drawer displaying distribution histograms, min/max/quartiles, and sample pattern categories.
3. **Cleaning & Operation Palette**:
   - Categorized library of allowlisted transformations: Header normalization, whitespace trimming, type casting, date parsing, missing-value imputation, deduplication, row filtering, column splitting/merging.
   - Parameter configuration pane with dynamic validation and immediate prospective impact estimates.
4. **Transformation Pipeline & History Drawer**:
   - Linear step sequence with enable/disable toggles, step reordering, and step removal.
   - Step diff metrics: Rows affected, columns modified, execution duration.
5. **Interactive Preview Pane**:
   - Side-by-side or split before-and-after view of dataset rows.
   - Visual highlighting of modified cells (subtle neutral tinting, not garish colors).
   - Filter to view "Only modified rows" or "Rows with warnings".
6. **Visualization Canvas**:
   - Configurable chart builder: Bar, line, histogram, scatter, and missingness matrix.
   - Axis bindings, aggregation methods, and explicit labeling for approximate or sampled visualizations.
7. **Export Drawer**:
   - Destination selector with overwrite warning.
   - Format options (CSV delimiter, line terminators, JSON layout).
   - Safe CSV mode (formula injection sanitization).
   - Export preview and summary log.
8. **Settings & AI Consent Center**:
   - Provider management (Local Ollama / OpenAI / Anthropic / Gemini).
   - OS credential storage status.
   - Outgoing payload inspector: View the exact JSON transmitted to AI before sending.

---

## 3. Interaction Standards & Feedback States

### A. State Taxonomy
- **Empty State**: Explains supported formats with an intuitive drop zone and recent file history.
- **Loading / Profiling State**: Non-blocking progress indicator with row/column counts processed and a safe "Cancel" button.
- **Success State**: Clear confirmation showing exact changes applied, runtime, and resulting dimensions.
- **Partial Success / Warning State**: Displays skipped rows or parse warnings in an expandable log table without dropping data silently.
- **Error State**: Actionable error diagnosis explaining the exact failure reason and steps to remediate.

### B. Destructive Action Protocol
- Operations that drop rows or alter types must display prospective row counts before applying.
- Source files are strictly read-only; the application never permits in-place overwriting of the original source file by default.
- Exporting to an existing path requires typing confirmation or explicit checkbox acknowledgment.

---

## 4. Typography & Color Tokens

- **Monospace Font**: For data values, formulas, schemas, JSON recipes, and code references (`JetBrains Mono`, `Consolas`, `monospace`).
- **Interface Font**: Modern, crisp sans-serif (`Inter`, `system-ui`, `-apple-system`, `sans-serif`).
- **Color Palette**:
  - Backgrounds: Neutral dark / light charcoal and slate (`#121417`, `#1A1D21`, `#22262B`).
  - Borders: Muted subtle dividing rules (`#2E343B`).
  - Text: High-contrast primary text (`#F0F3F6`), secondary muted text (`#9BA3AF`).
  - Semantic Accents:
    - Information: Slate Blue (`#3B82F6`)
    - Success: Muted Emerald (`#10B981`)
    - Warning: Amber (`#F59E0B`)
    - Destructive / Error: Rust Rose (`#EF4444`)
