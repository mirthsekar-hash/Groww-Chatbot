---
name: Groww RAG Dark
colors:
  surface: '#10131a'
  surface-dim: '#10131a'
  surface-bright: '#363940'
  surface-container-lowest: '#0b0e14'
  surface-container-low: '#191c22'
  surface-container: '#1d2026'
  surface-container-high: '#272a31'
  surface-container-highest: '#32353c'
  on-surface: '#e1e2eb'
  on-surface-variant: '#bacac1'
  inverse-surface: '#e1e2eb'
  inverse-on-surface: '#2e3037'
  outline: '#85948c'
  outline-variant: '#3c4a43'
  surface-tint: '#2fe0aa'
  primary: '#44edb7'
  on-primary: '#003828'
  primary-container: '#00d09c'
  on-primary-container: '#00533c'
  inverse-primary: '#006c4f'
  secondary: '#c4c6ce'
  on-secondary: '#2d3037'
  secondary-container: '#464950'
  on-secondary-container: '#b6b8c0'
  tertiary: '#ced3df'
  on-tertiary: '#2c313a'
  tertiary-container: '#b3b7c3'
  on-tertiary-container: '#434852'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#59fdc5'
  primary-fixed-dim: '#2fe0aa'
  on-primary-fixed: '#002116'
  on-primary-fixed-variant: '#00513b'
  secondary-fixed: '#e1e2ea'
  secondary-fixed-dim: '#c4c6ce'
  on-secondary-fixed: '#191c22'
  on-secondary-fixed-variant: '#44474d'
  tertiary-fixed: '#dee2ef'
  tertiary-fixed-dim: '#c2c6d2'
  on-tertiary-fixed: '#171c24'
  on-tertiary-fixed-variant: '#424751'
  background: '#10131a'
  on-background: '#e1e2eb'
  surface-variant: '#32353c'
typography:
  headline-xl:
    fontFamily: Manrope
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Manrope
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Manrope
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  headline-lg-mobile:
    fontFamily: Manrope
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  container-padding-desktop: 32px
  container-padding-mobile: 16px
  gutter: 24px
  max-width: 1280px
---

## Brand & Style

The brand personality for this design system is **Professional, Intellectual, and AI-Native**. It transitions the established reliability of the light mode into a focused, low-distraction environment tailored for deep research and financial analysis.

The design style is **Modern Minimalist with Neon-Accents**. It moves away from the typical "pure black" dark modes to a more sophisticated deep charcoal palette, reducing eye strain while maintaining a high sense of premium quality. Depth is communicated through tonal layering and subtle luminosity rather than physical shadows. The "AI-native" feel is reinforced through glowing status indicators and razor-sharp borders that suggest precision and technological sophistication.

## Colors

This design system utilizes a tiered dark palette to establish hierarchy without glare.
- **Surface (#0B0E14):** The primary canvas. A deep, near-black charcoal that provides the foundation for the entire interface.
- **Container (#1A1D23):** Used for elevated surfaces like chat bubbles and cards to create soft separation from the background.
- **Primary Accent (#00D09C):** The signature Groww Green, used sparingly for calls to action, active states, and AI indicators.
- **Typography:** Bright white is reserved for high-priority headings to ensure maximum legibility, while cool grey (#E5E7EB) is used for body text to reduce contrast fatigue.

## Typography

The typography strategy pairs **Manrope** for structural elements and **Inter** for data-dense reading.
- **Headlines:** Manrope is used for all headings to provide a modern, geometric feel that implies stability.
- **Body:** Inter is chosen for its exceptional legibility in dark mode, particularly for long-form AI responses and financial data.
- **Scale:** High-level headers use tighter letter spacing to maintain a "compact" premium look, while labels utilize increased tracking for clarity at small sizes.

## Layout & Spacing

The design system employs a **12-column fluid grid** for desktop and a **4-column grid** for mobile. 
- **Rhythm:** An 8px-based spacing system (incremented by 4px units) ensures mathematical harmony between components.
- **Margins:** Desktop views utilize generous side margins (32px) to focus the user's eye on the central chat and research area.
- **AI Specificity:** The chat interface uses a maximum-width constraint (800px) for the main dialogue thread to ensure optimal line length for readability, while auxiliary source cards occupy the right-hand gutters on larger screens.

## Elevation & Depth

Depth in this design system is achieved through **Tonal Layering** and **Low-Contrast Outlines**. 
- **Layers:** Objects do not cast heavy shadows. Instead, higher-elevation components use the lighter Slate (#1A1D23) or Dark Slate (#242932) backgrounds.
- **Borders:** Every container features a 1px border using a subtle cool-grey at 10% opacity. This creates a "glass-edge" effect that feels precise and architectural.
- **Glows:** A 12px-16px blur radius "Neon Glow" is applied exclusively to active AI status indicators and primary buttons using the Groww Green at low opacity, suggesting that the AI is "powered on."

## Shapes

The shape language is **Refined and Balanced**. 
- **Containers:** Standard cards and chat bubbles use a 0.5rem (8px) radius. 
- **Large Components:** Main content areas and large source panels use a 1rem (16px) radius for a softer, more modern aesthetic.
- **Interactive Elements:** Small buttons and tags use 0.5rem to maintain consistency, while AI-generated "pills" or status tags may use a full pill-shape for distinct visual categorization.

## Components

- **Chat Bubbles:**
  - *User:* Surface background (#0B0E14) with a subtle teal border (1px, 20% opacity) to distinguish the user's input.
  - *AI:* Slate background (#1A1D23) with no border, creating a solid, authoritative feel.
- **Source Cards:** Dark slate background with a 2px left-accent border in Groww Green. These cards should feature metadata (e.g., "Source: Annual Report") in the Label-MD style.
- **Buttons:** Primary buttons use a solid Groww Green background with black text. On hover, a subtle green outer glow (8px blur) is activated.
- **AI Status Indicators:** A circular green dot with a pulsing neon glow (0% to 40% opacity) to indicate the RAG engine is processing.
- **Navigation:** A persistent sidebar in #0B0E14 with a vertical 1px divider. Active states are indicated by text color shifting to Bright White and a small green vertical notch on the far left.
- **Input Field:** A floating search/query bar with a slate background and a 1px border that glows green when focused.