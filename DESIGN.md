---
version: "alpha"
name: Bitget Wallet Mobile Design System
description: Mobile-first Web3 wallet design system distilled from Bitget Wallet app-store surfaces and the official Bitget Wallet web brand.

colors:
  primary: "#62EEF8"
  secondary: "#00C2B7"
  tertiary: "#FE5B79"
  neutral: "#17171A"

  brand-cyan: "#62EEF8"
  brand-teal: "#00C2B7"
  brand-cyan-deep: "#00BBE0"
  brand-cyan-dark: "#00768E"
  brand-ink: "#001F29"
  brand-blue: "#2489FF"
  brand-purple: "#9C60FF"
  brand-warning: "#FF910E"
  brand-yellow: "#FFC400"
  brand-danger: "#FE5B79"

  canvas: "#17171A"
  surface: "#202024"
  surface-raised: "#252529"
  surface-panel: "#2E2E33"
  surface-strong: "#36363D"
  surface-teal: "#084456"
  surface-teal-soft: "#03313A"
  surface-light: "#FFFFFF"
  surface-light-muted: "#F8F8F9"

  text-primary: "#E5E5E5"
  text-strong: "#FFFFFF"
  text-secondary: "#9D9DA6"
  text-tertiary: "#707076"
  text-muted: "#59595E"
  text-on-accent: "#001F29"
  text-on-light: "#0D0E0E"

  border: "#2E2E33"
  border-strong: "#36363D"
  border-teal: "#2D3739"
  border-alpha: "#2D3739"
  overlay-dark: "#0B0016"
  overlay-scrim: "#000000"

  success: "#00C2B7"
  success-bg: "#003B3A"
  warning: "#FF910E"
  error: "#FE5B79"

typography:
  hero-display:
    fontFamily: "HarmonyOS Sans"
    fontSize: 36px
    fontWeight: "600"
    lineHeight: 40px
    letterSpacing: 0px
  display-lg:
    fontFamily: "HarmonyOS Sans"
    fontSize: 32px
    fontWeight: "600"
    lineHeight: 38px
    letterSpacing: 0px
  heading-lg:
    fontFamily: "HarmonyOS Sans"
    fontSize: 28px
    fontWeight: "600"
    lineHeight: 34px
    letterSpacing: 0px
  heading-md:
    fontFamily: "HarmonyOS Sans"
    fontSize: 24px
    fontWeight: "700"
    lineHeight: 32px
    letterSpacing: 0px
  heading-sm:
    fontFamily: "HarmonyOS Sans"
    fontSize: 20px
    fontWeight: "600"
    lineHeight: 30px
    letterSpacing: 0px
  body-lg:
    fontFamily: "HarmonyOS Sans"
    fontSize: 18px
    fontWeight: "400"
    lineHeight: 26px
    letterSpacing: 0.25px
  body-md:
    fontFamily: "HarmonyOS Sans"
    fontSize: 16px
    fontWeight: "400"
    lineHeight: 24px
    letterSpacing: 0px
  body-md-medium:
    fontFamily: "HarmonyOS Sans"
    fontSize: 16px
    fontWeight: "500"
    lineHeight: 24px
    letterSpacing: 0px
  body-sm:
    fontFamily: "HarmonyOS Sans"
    fontSize: 14px
    fontWeight: "400"
    lineHeight: 21px
    letterSpacing: -0.5px
  body-sm-medium:
    fontFamily: "HarmonyOS Sans"
    fontSize: 14px
    fontWeight: "500"
    lineHeight: 21px
    letterSpacing: -0.5px
  caption:
    fontFamily: "HarmonyOS Sans"
    fontSize: 12px
    fontWeight: "400"
    lineHeight: 16px
    letterSpacing: 0px
  caption-medium:
    fontFamily: "HarmonyOS Sans"
    fontSize: 12px
    fontWeight: "500"
    lineHeight: 16px
    letterSpacing: 0px
  micro:
    fontFamily: "HarmonyOS Sans"
    fontSize: 10px
    fontWeight: "400"
    lineHeight: 15px
    letterSpacing: -0.5px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 20px
  xl: 24px
  xxl: 32px
  xxxl: 40px
  section: 64px
  section-lg: 80px
  screen-gutter: 20px

rounded:
  xs: 2px
  sm: 4px
  md: 8px
  lg: 12px
  xl: 16px
  xxl: 20px
  xxxl: 24px
  card: 30px
  pill: 50px
  full: 9999px

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.text-on-accent}"
    rounded: "{rounded.pill}"
    typography: "{typography.body-sm-medium}"
    height: 40px
    padding: "0 20px"
  button-secondary:
    backgroundColor: "{colors.surface-teal}"
    textColor: "{colors.text-strong}"
    rounded: "{rounded.pill}"
    typography: "{typography.body-sm-medium}"
    height: 40px
    padding: "0 20px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.pill}"
    typography: "{typography.body-sm-medium}"
    height: 40px
    padding: "0 16px"
  wallet-balance-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.xxxl}"
    padding: "{spacing.xl}"
  asset-row:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.lg}"
    padding: "{spacing.md}"
    typography: "{typography.body-sm}"
  quick-action-tile:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.xl}"
    padding: "{spacing.md}"
    typography: "{typography.caption-medium}"
  bottom-tab-bar:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-secondary}"
    height: 64px
  modal-sheet:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.xxxl}"
---

## Overview

Bitget Wallet presents itself as a mobile-first Web3 finance product: compact, secure, and action-heavy, but visually softened by pill controls and large rounded cards. The brand voice is "Crypto for Everyone", and the product UI follows that promise: trading, earn, spend, transfer, DApps, NFTs, and security are grouped into approachable modules rather than exposed as raw protocol complexity.

The official web surface anchors in a deep dark canvas (`{colors.canvas}`) with bright cyan action color (`{colors.brand-cyan}`). App-store screenshots and product copy reinforce a consumer wallet structure: balance overview, asset lists, token discovery, swaps, earn campaigns, Web3 browser, crypto card/payment, and security assurance. The system should feel like a trusted fintech app with Web3 density underneath - not a neon trading terminal and not a playful consumer wallet.

**Key Characteristics:**
- Dark fintech canvas (`{colors.canvas}`) with raised charcoal surfaces (`{colors.surface}`, `{colors.surface-raised}`).
- Cyan primary action (`{colors.brand-cyan}`) paired with dark teal ink (`{colors.text-on-accent}`), used for Download, Connect, Start, Continue, and primary wallet actions.
- HarmonyOS Sans as the observed brand typeface, backed by Inter and platform system sans.
- Mobile-first hierarchy: 36px compact hero displays, 24px section headers, 16px body, 14px dense labels, and 12px metadata.
- Rounded financial modules: 20-24px standard cards, 30-40px promotional/payment cards, and full pills for actions, filters, and status.
- App navigation relies on bottom tabs, action grids, token rows, and sheet-based flows instead of desktop-style sidebars.
- Brand accents beyond cyan - red, orange, yellow, blue, purple - are semantic or token-category signals, not general decoration.

## Colors

> Source pages: `web3.bitget.com/en`, Apple App Store listing for Bitget Wallet, and Google Play listing for Bitget Wallet. Web CSS exposes the most reliable token values; mobile app details are inferred from official store screenshots and product copy.

### Brand & Accent

- **Brand Cyan** (`{colors.brand-cyan}`): Primary action color. Used for Download, Connect Wallet, Start Trading, active tabs, focused controls, and major confirmation buttons.
- **Brand Teal** (`{colors.brand-teal}`): Success and positive movement accent. Used for active states, success badges, positive APY/earn moments, and confirmed transaction feedback.
- **Brand Cyan Deep** (`{colors.brand-cyan-deep}`): Stronger cyan for selected tabs, price-chart emphasis, and dark-surface highlights.
- **Brand Cyan Dark** (`{colors.brand-cyan-dark}`): Structural teal-blue used for secondary emphasis, outline states, and dense information surfaces.
- **Brand Ink** (`{colors.brand-ink}`): Text on cyan and pale teal surfaces. It gives bright actions a serious financial tone.
- **Brand Danger** (`{colors.brand-danger}`): Negative movement, risk, failed transaction, and warning copy requiring immediate attention.
- **Brand Warning** (`{colors.brand-warning}`): Risk education, pending transactions, hot-token labels, and APY caveats.
- **Brand Blue** (`{colors.brand-blue}`): Informational market, chain, and discovery accents.
- **Brand Purple** (`{colors.brand-purple}`): NFT, rewards, campaign, and Web3 discovery accents.

### Surface

- **Canvas** (`{colors.canvas}`): Primary dark background for app shells and marketing surfaces.
- **Surface** (`{colors.surface}`): Navigation bars, bottom tabs, sheets, and standard raised app areas.
- **Surface Raised** (`{colors.surface-raised}`): Wallet cards, action grids, search areas, and segmented panels.
- **Surface Panel** (`{colors.surface-panel}`): Dividers, bordered panels, compact containers, and low-emphasis card chrome.
- **Surface Strong** (`{colors.surface-strong}`): Pressed, selected, and nested-surface states.
- **Surface Teal** (`{colors.surface-teal}`): Secondary action fill on dark surfaces.
- **Surface Light** (`{colors.surface-light}`): Store screenshot mockups, QR cards, legal white panels, and occasional light-mode modules.

### Text

- **Text Primary** (`{colors.text-primary}`): Primary dark-mode body and heading text.
- **Text Strong** (`{colors.text-strong}`): Maximum contrast text on dark surfaces.
- **Text Secondary** (`{colors.text-secondary}`): Descriptions, subtitles, token metadata, and inactive labels.
- **Text Tertiary** (`{colors.text-tertiary}`): Timestamps, helper text, row subtitles, and low-priority tab labels.
- **Text Muted** (`{colors.text-muted}`): Disabled states and deep footer metadata.
- **Text On Accent** (`{colors.text-on-accent}`): Button text over cyan actions.

### Semantic

- **Success** (`{colors.success}`): Confirmed transaction, positive APY, connected state, and safe status.
- **Success Background** (`{colors.success-bg}`): Soft success badges and non-blocking confirmations.
- **Warning** (`{colors.warning}`): Risk, pending, campaign urgency, or market caution.
- **Error** (`{colors.error}`): Failed transaction, invalid address, insufficient balance, and negative price movement.

## Typography

### Font Family

**HarmonyOS Sans** is the observed brand font family across the official web interface. It has a neutral geometric character that works well for dense wallet screens, token symbols, and high-contrast buttons. Use Inter and platform system fonts as fallbacks.

The system uses medium weights aggressively for labels and navigation. This gives small mobile controls enough strength on dark surfaces. Large marketing copy is compact rather than editorial: Bitget Wallet does not use exaggerated 80px brand headlines inside the app language; it prefers efficient mobile hierarchy.

### Hierarchy

| Token | Size | Weight | Line Height | Letter Spacing | Use |
|---|---:|---:|---:|---:|---|
| `{typography.hero-display}` | 36px | 600 | 40px | 0 | Mobile app hero, major page opener |
| `{typography.display-lg}` | 32px | 600 | 38px | 0 | Balance amount, campaign hero |
| `{typography.heading-lg}` | 28px | 600 | 34px | 0 | Feature title, onboarding step title |
| `{typography.heading-md}` | 24px | 700 | 32px | 0 | Screen title, important card title |
| `{typography.heading-sm}` | 20px | 600 | 30px | 0 | Card title, module title |
| `{typography.body-lg}` | 18px | 400 | 26px | 0.25px | Lead description, feature subtitle |
| `{typography.body-md}` | 16px | 400 | 24px | 0 | Primary body and row titles |
| `{typography.body-md-medium}` | 16px | 500 | 24px | 0 | Navigation and active row labels |
| `{typography.body-sm}` | 14px | 400 | 21px | -0.5px | Dense body, helper text, asset metadata |
| `{typography.body-sm-medium}` | 14px | 500 | 21px | -0.5px | Buttons, chips, table labels |
| `{typography.caption}` | 12px | 400 | 16px | 0 | Metadata, timestamps, micro descriptions |
| `{typography.caption-medium}` | 12px | 500 | 16px | 0 | Badges, quick-action labels |
| `{typography.micro}` | 10px | 400 | 15px | -0.5px | Tiny status labels and compact notices |

### Principles

- **Compact mobile hierarchy:** Large text should earn its space. Balance totals and screen openers can use 32-36px; repeated modules should step down quickly.
- **Medium label weight:** Buttons, filters, tabs, and token labels use 500 to remain legible on dark surfaces.
- **Numeric clarity:** Balances, APY, fiat equivalents, and token prices use tabular-number rendering when available.
- **No decorative typography:** Emphasis comes from weight, color, and placement, not multiple typefaces.
- **Letter-spacing restraint:** The web surface uses slight negative tracking on dense labels; keep this limited to 14px labels and avoid tightening long financial values.

## Layout

### Spacing System

- **Base unit:** 4px, with 8px as the practical rhythm.
- **Tokens:** `{spacing.xxs}` (4px), `{spacing.xs}` (8px), `{spacing.sm}` (12px), `{spacing.md}` (16px), `{spacing.lg}` (20px), `{spacing.xl}` (24px), `{spacing.xxl}` (32px), `{spacing.xxxl}` (40px), `{spacing.section}` (64px), `{spacing.section-lg}` (80px).
- **Mobile gutters:** `{spacing.screen-gutter}` (20px) on web/mobile marketing and 16-20px in app screens.
- **Module rhythm:** Wallet app screens use 12-16px gaps between functional modules; marketing sections can expand to 64-80px.
- **Card padding:** Balance and wallet cards use 20-24px; quick-action tiles use 12-16px; dense token rows use 12-16px horizontal padding.

### Mobile Screen Structure

- App screens use a single-column stack: top app bar, primary wallet/balance card, quick-action row, feed/module list, bottom navigation.
- Wallet balance modules should sit near the top and expose primary actions immediately: Receive, Send, Swap, Buy, Earn.
- Token rows are full-width list items with token icon left, symbol/name stack, balance/fiat stack right, and optional price movement metadata.
- Discovery screens use card grids or horizontal carousels for campaigns, DApps, NFTs, and airdrops.
- Swap and transfer flows should use bottom sheets for token selection, chain selection, network fee details, confirmation, and error recovery.

### Web Brand Layout

- Official web marketing uses sticky dark glass navigation, a compact mobile header at 44px, and a 64px desktop header.
- Desktop marketing sections are full-viewport feature bands with large device imagery and centered product promises.
- The website is evidence for color, type, and brand tone; the app design should translate those into denser mobile wallet patterns.

### Whitespace Philosophy

Bitget Wallet balances friendliness with financial density. Use enough whitespace to avoid crypto intimidation, but do not turn wallet screens into sparse marketing pages. Cards can be large when they contain balance, security, payment, or earn decisions. Token lists, DApp lists, and transaction histories should be compact and scannable.

## Elevation & Depth

The system is mostly flat, with depth coming from dark surface layering, blur, and rounded containers. Heavy shadows are rare on the official web surface and should not become a default app style.

| Level | Treatment | Use |
|---|---|---|
| 0 Flat | `{elevation.flat}` plus surface contrast | Lists, rows, action tiles |
| 1 Raised | `{elevation.raised}` | Sticky bottom navigation, floating utility buttons |
| 2 Card | `{elevation.card}` | Menus, QR download panels, raised wallet modules |
| 3 Modal | `{elevation.modal}` | Confirmation sheets, token selector sheets, security prompts |
| Focus | `{elevation.focus}` | Focus ring, selected controls, wallet connection states |

### Decorative Depth

- Use cyan glow sparingly around security, connected, and success moments.
- Device mockups and app-store screenshots may carry stronger shadows, but product UI cards should remain mostly flat.
- Avoid neon bloom around every button. Cyan is a system action color, not a decorative light source.

## Shapes

### Border Radius Scale

| Token | Value | Use |
|---|---:|---|
| `{rounded.xs}` | 2px | Tiny dividers, progress ticks |
| `{rounded.sm}` | 4px | Compact chips, small inline controls |
| `{rounded.md}` | 8px | Inputs, small menus, QR frame internals |
| `{rounded.lg}` | 12px | Standard list cards, popover panels |
| `{rounded.xl}` | 16px | Quick-action tiles, DApp cards |
| `{rounded.xxl}` | 20px | Standard wallet feature cards |
| `{rounded.xxxl}` | 24px | Balance cards, sheet handles, major panels |
| `{rounded.card}` | 30px | Payment cards, promotional finance cards |
| `{rounded.pill}` | 50px | Buttons, filter chips, primary actions |
| `{rounded.full}` | 9999px | Avatars, token icons, circular icon buttons |

### Geometry Principles

- Buttons are always pill-like. A squared primary action feels off-brand.
- Wallet cards and finance modules prefer 20-30px rounding; dense token rows use 12-16px.
- Bottom sheets use 24px top corners and square bottom edges.
- Token icons, chain icons, avatars, and network marks are circular unless the asset brand requires a custom silhouette.

## Components

> Per the no-hover policy, hover states are not documented. Default, active, pressed, disabled, loading, and error states are documented where relevant.

### Buttons

**`button-primary`** - Main cyan pill action.
- Background `{colors.brand-cyan}`, text `{colors.text-on-accent}`, typography `{typography.body-sm-medium}`, height 40px, padding `0 20px`, rounded `{rounded.pill}`.
- Use for Download, Continue, Confirm Swap, Send, Receive, Connect Wallet, Start Trading.
- Pressed state darkens to `{colors.brand-teal}`.
- Disabled state uses `{colors.surface-panel}` background and `{colors.text-muted}` text.

**`button-secondary`** - Dark teal secondary pill.
- Background `{colors.surface-teal}`, text `{colors.text-strong}`, typography `{typography.body-sm-medium}`, height 40px, padding `0 20px`, rounded `{rounded.pill}`.
- Use for supporting CTAs such as Security Assurance, View Details, Review Route, or Learn More.

**`button-ghost`** - Text/icon action on dark surface.
- Background transparent, text `{colors.text-primary}`, typography `{typography.body-sm-medium}`, height 40px, padding `0 16px`, rounded `{rounded.pill}`.
- Use in app bars, optional actions, and low-priority rows.

**`button-icon-circular`** - Utility icon button.
- 40x40px desktop and 44x44px mobile touch target, background `{colors.surface-raised}`, icon `{colors.text-primary}`, rounded `{rounded.full}`.
- Use for scan, notifications, settings, copy, close, and more actions.

### Wallet & Asset Components

**`wallet-balance-card`** - Primary account summary card.
- Background `{colors.surface}`, text `{colors.text-primary}`, rounded `{rounded.xxxl}`, padding `{spacing.xl}`.
- Top row: wallet/account name, network selector, visibility toggle.
- Center: balance amount in `{typography.display-lg}` or `{typography.hero-display}`.
- Bottom: quick actions or PnL/portfolio chips.

**`asset-row`** - Token holding list item.
- Background `{colors.canvas}` or transparent inside a list, rounded `{rounded.lg}`, padding `{spacing.md}`.
- Left: circular token icon 36-40px, token symbol `{typography.body-md-medium}`, token name/network `{typography.caption}`.
- Right: token amount `{typography.body-sm-medium}`, fiat value `{typography.caption}`, and optional price change.

**`token-price-row`** - Market/discovery token row.
- Same base as `asset-row`, with right-side price and change badge.
- Positive change uses `{colors.success}`; negative change uses `{colors.error}`; neutral metadata uses `{colors.text-tertiary}`.

**`chain-pill`** - Network selector chip.
- Background `{colors.surface-raised}`, text `{colors.text-primary}`, border `1px solid {colors.border}`, rounded `{rounded.pill}`, typography `{typography.caption-medium}`.
- Use in wallet header, swap route, address selector, and DApp connection screens.

### Actions & Navigation

**`quick-action-tile`** - Send/Receive/Swap/Buy/Earn tile.
- Background `{colors.surface-raised}`, text `{colors.text-primary}`, rounded `{rounded.xl}`, padding `{spacing.md}`.
- Icon top, label below in `{typography.caption-medium}`.
- Active/pressed state uses `{colors.surface-strong}` and icon `{colors.brand-cyan}`.

**`bottom-tab-bar`** - Persistent mobile navigation.
- Background `{colors.surface}`, height 64px plus safe-area inset, top border `1px solid {colors.border}`.
- Typical tabs: Home, Market, Swap, Discover, Assets.

**`bottom-tab-item-active`** - Active bottom tab state.
- Icon and label `{colors.brand-cyan}`, label `{typography.caption-medium}`.
- Inactive items use `{colors.text-tertiary}`.

**`top-app-bar`** - Mobile header.
- Height 44-56px, background `{colors.canvas}` or translucent `{colors.overlay-dark}`, text `{colors.text-primary}`.
- Hosts wallet selector, scan, search, notifications, settings, and connect status.

### Inputs, Search, and Filters

**`search-input`** - Token/DApp/search field.
- Background `{colors.surface-raised}`, text `{colors.text-primary}`, placeholder `{colors.text-tertiary}`, rounded `{rounded.pill}` or `{rounded.lg}`, height 40px.
- Focus state uses `1px solid {colors.brand-cyan}` and `{elevation.focus}`.

**`amount-input`** - Swap/send numeric field.
- Background `{colors.surface}`, text `{colors.text-primary}`, rounded `{rounded.xxl}`, padding `{spacing.lg}`, large numeric typography `{typography.display-lg}`.
- Secondary line shows fiat estimate and balance.
- Error state adds `{colors.error}` label and border.

**`filter-chip`** - Market, token, NFT, and DApp category chip.
- Inactive: background `{colors.surface-raised}`, text `{colors.text-secondary}`, rounded `{rounded.pill}`, padding `6px 12px`.
- Active: background `{colors.brand-cyan}`, text `{colors.text-on-accent}`.

### Trading, Earn, and Payment

**`swap-panel`** - Swap route container.
- Background `{colors.surface}`, rounded `{rounded.xxxl}`, padding `{spacing.lg}`.
- Includes from/to token selectors, amount fields, route summary, network fee, and primary confirm button.
- Route details should be collapsed by default but accessible before confirmation.

**`earn-card`** - Earn/APY opportunity card.
- Background `{colors.surface-raised}`, rounded `{rounded.xxl}`, padding `{spacing.lg}`.
- APY uses `{colors.success}` when promotional or positive; risk/caveat text uses `{colors.text-tertiary}`.
- Include protocol/network icon, asset name, estimated APY, and action button.

**`payment-card`** - Crypto card/spend module.
- Background may use `{colors.brand-ink}` or a dark gradient using `{colors.surface-teal}` and `{colors.canvas}`.
- Rounded `{rounded.card}`, padding `{spacing.xl}`, text `{colors.text-strong}`.
- Should feel premium but not flashy; cyan appears as an accent line or CTA, not a full-card glow.

**`qr-card`** - Receive/scan QR panel.
- Background `{colors.surface-light}`, text `{colors.text-on-light}`, rounded `{rounded.xxl}`, padding `{spacing.xl}`.
- QR code sits on white with 8-12px internal padding; address copy controls sit below.

### Security & Status

**`security-banner`** - Safety/protection notice.
- Background `{colors.surface-teal-soft}` or `{colors.surface-teal}`, text `{colors.text-strong}`, rounded `{rounded.xxl}`, padding `{spacing.lg}`.
- Used for MPC, smart wallet technology, protection fund, scam warnings, or DApp risk.

**`status-pill-success`** - Connected, available, safe.
- Background `{colors.success-bg}`, text `{colors.success}`, rounded `{rounded.pill}`, typography `{typography.caption-medium}`, padding `4px 10px`.

**`status-pill-warning`** - Pending, review, caution.
- Background `rgba(255,145,14,0.16)`, text `{colors.warning}`, rounded `{rounded.pill}`, typography `{typography.caption-medium}`.

**`status-pill-error`** - Failed, risky, invalid.
- Background `rgba(254,91,121,0.16)`, text `{colors.error}`, rounded `{rounded.pill}`, typography `{typography.caption-medium}`.

### Sheets & Modals

**`modal-sheet`** - Bottom sheet for mobile flows.
- Background `{colors.surface}`, text `{colors.text-primary}`, top corners `{rounded.xxxl}`, shadow `{elevation.modal}`.
- Handle is 36x4px, `{colors.surface-strong}`, rounded `{rounded.full}`.
- Use for token selection, network switching, transaction confirmation, password/security prompts, and DApp permission review.

**`permission-sheet`** - DApp connection approval.
- Based on `modal-sheet`, with DApp icon/title, requested networks/accounts, risk note, and two actions.
- Primary action uses `button-primary`; cancel uses `button-ghost` or `button-secondary` depending on risk.

### Marketing & Store Components

**`app-store-screenshot-frame`** - Promotional app screenshot frame.
- Dark or cyan campaign background with device screenshot centered.
- Use rounded phone frame, high contrast title copy, and one product promise per image.
- Do not mix too many features in a single screenshot; each frame should sell one action: Trade, Earn, Spend, Transfer, Discover, Secure.

**`download-header`** - Website/mobile download bar.
- Mobile height 44px, background `rgba(23,23,26,0.80)` with blur, left logo, right `button-primary` and menu icon.
- Desktop height 64px with link list and Download CTA.

## Do's and Don'ts

### Do

- Use `{colors.brand-cyan}` as the dominant CTA across wallet, trading, earn, and onboarding flows.
- Keep dark surfaces layered: `{colors.canvas}` page, `{colors.surface}` module, `{colors.surface-raised}` nested controls.
- Use rounded cards to make complex crypto tasks feel contained and reversible.
- Show risk, network, fee, and route context before irreversible actions.
- Keep token rows compact and scannable; crypto users compare many assets quickly.
- Use bottom sheets for selection and confirmation instead of full-screen detours when the user is mid-flow.
- Treat "Crypto for Everyone" as an accessibility principle: clear labels, plain-language confirmations, and obvious recovery paths.

### Don't

- Do not use cyan as a decorative wash everywhere; it loses CTA authority.
- Do not make all cards glow. Most wallet surfaces should be flat with surface contrast.
- Do not hide network fees, routes, or risk warnings behind small text only.
- Do not use light-mode cards as the default app language; white is reserved for QR, legal, store, or special content.
- Do not introduce multiple display fonts or Web3 novelty fonts.
- Do not over-round dense token rows beyond readability; reserve very large radius for cards, sheets, and payment modules.

## Responsive Behavior

### Breakpoints

| Name | Width | Key Changes |
|---|---:|---|
| Small Mobile | < 390px | Single-column app shell, 16px gutters, compact 32px balance display, icon-only dense actions when needed |
| Mobile | 390-767px | Primary target; 20px gutters, bottom tabs, full-width cards, sheets for selection |
| Tablet | 768-1023px | Two-column card grids, side-by-side balance and activity modules, persistent secondary panels |
| Desktop Web | 1024-1279px | Marketing/product layout with sticky nav, expanded sections, device mockups |
| Wide Desktop | >= 1280px | Large web gutters, full feature bands, richer app screenshot compositions |

### Touch Targets

- Primary and secondary buttons: 40px minimum, 44px preferred in high-frequency mobile flows.
- Icon buttons: 40x40px minimum, 44x44px for scan, close, and navigation controls.
- Token rows: 56px minimum, 64-72px when displaying price, chain, or balance metadata.
- Bottom tab items: 56px minimum plus safe-area inset.

### Collapsing Strategy

- Top navigation on web collapses to logo, Download, and menu at mobile width.
- App action grids render 4-up on standard mobile, 3-up or horizontal-scroll when labels are long.
- Market and DApp cards move from 2-column grids to horizontal carousels on small mobile.
- Swap route details stay collapsed until review, but fee/risk summaries remain visible.
- Long wallet addresses truncate in the middle, never at the end only.

### Image Behavior

- App screenshots should use real product UI inside device frames, not abstract crypto art.
- Token and chain icons remain circular at 24-40px.
- Campaign imagery can be more expressive, but must preserve CTA contrast and avoid obscuring financial data.

## Iteration Guide

1. Start with the mobile wallet shell: top bar, balance card, quick actions, asset list, bottom tab bar.
2. Use token references directly (`{colors.brand-cyan}`, `{rounded.pill}`, `{typography.body-sm-medium}`) when adding components.
3. Keep primary actions cyan and singular per screen; secondary actions use dark teal or ghost styling.
4. Add new states as explicit component variants: `-active`, `-pressed`, `-disabled`, `-loading`, `-error`.
5. Run `npx @google/design.md lint DESIGN.md` after edits.
6. When generating screens from this system, prioritize wallet clarity over marketing drama.
7. Validate transaction flows with realistic data: long token names, long addresses, multiple chains, insufficient balance, high slippage, and pending confirmations.

## Known Gaps

- Exact in-app production token values are not publicly exported; some mobile-app component details are inferred from official app-store screenshots and web brand tokens.
- Motion timing is not formalized. Default to 150-200ms ease for button/sheet transitions and 250-350ms for modal sheet entrance.
- Iconography is not fully extracted. Use clean rounded line icons for utilities and official chain/token marks for assets.
- Light mode is not documented as a complete app theme. White surfaces are treated as special-purpose cards unless an official light wallet theme is supplied.
- Advanced chart colors, candlestick palettes, and token-category colors need a dedicated market-screen audit if charting becomes central.