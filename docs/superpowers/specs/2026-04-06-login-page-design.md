# JobRadar Login Page Design

## Summary

This spec defines a redesigned login page for JobRadar.

The first version is UI-only and intentionally does not implement real authentication. The page is for internal members and private preview usage, so it should feel professional, warm, and trustworthy rather than public-growth-oriented or overly minimal.

The approved direction combines:

- the layout structure of the "professional SaaS" mockup
- the warmer color mood of the "career product" mockup
- a single account/password login form
- two checkboxes: `记住我` and `自动登录`

## Goals

- Replace the current overly plain login experience with a more polished page.
- Present JobRadar as a mature internal job intelligence workspace.
- Preserve a clear path to add real login logic later without redesigning the page.
- Keep the page usable for desktop-first internal workflows while remaining responsive on mobile.

## Non-Goals

- Implement real authentication APIs.
- Implement session, JWT, cookie, or permission logic.
- Add OAuth or third-party identity providers.
- Add registration, password reset, or account recovery.

## Product Context

The login page is for the project owner and a small number of internal members.

This means the page should:

- avoid consumer-style acquisition patterns
- avoid obvious registration or trial CTAs
- communicate product value without turning into a marketing homepage
- signal that access is limited to approved internal accounts

## Design Direction

### Visual Tone

The page should feel:

- professional
- warm
- trustworthy
- product-oriented
- internal rather than public-marketing-driven

It should avoid:

- cold generic admin login styling
- overly dark sci-fi visuals
- aggressive growth/product marketing language
- excessive gradients, glow, or dashboard clutter

### Layout

The page uses a two-column layout on desktop.

- Left column: product value, short supporting copy, and lightweight product context.
- Right column: login card with account/password form.

On small screens, the layout collapses into a vertical stack.

### Color Strategy

- Large surfaces: warm white / pale cream / soft neutral backgrounds
- Primary action: blue
- Accent color: orange
- Body text: dark slate or dark warm gray
- Borders: low-contrast light gray
- Error states: soft red, not saturated warning red

Blue remains the primary action color to preserve trust and clarity. Orange is used only as an accent in supporting content and visual emphasis.

## Information Architecture

### Top Brand Area

The page should show a lightweight brand area only.

- Brand: `JobRadar`
- Status label: `Private Preview`

It should not include:

- top navigation
- registration links
- try-now CTAs
- external identity provider buttons

### Left Content Area

The left side should communicate product value with moderate information density.

#### Primary Headline

`更快发现值得投递的岗位`

#### Supporting Copy

`聚合、筛选、评分与跟踪，集中管理你的求职信息流。`

#### Value Points

- `多来源岗位聚合，减少重复搜岗`
- `统一筛选与评分，快速定位优先机会`
- `申请流程可追踪，避免信息散落`

#### Lightweight Product Stats

The initial design includes two lightweight stats or status cards:

- `74k+ 岗位数据池`
- `55k+ TATA 覆盖`

These should read as product context rather than full dashboard widgets.

## Login Card Structure

The right-side card is a pure account/password login form.

### Card Content

- Title: `登录 JobRadar`
- Description: `使用内测账号继续访问岗位总览、申请流程看板与配置中心。`
- Field 1: `账号`
- Field 2: `密码`
- Checkbox 1: `记住我`
- Checkbox 2: `自动登录`
- Primary button: `登录`
- Footer note: `当前为内测版本，仅限已开通账号的成员访问。`
- Footer help: `如需开通，请联系管理员。`

### Explicit Exclusions

The card must not include:

- GitHub login
- Google login
- any OAuth buttons
- secondary login method buttons
- registration links
- forgot-password flows in the first version

## Interaction Design

### Default State

- Inputs have generous spacing and consistent height.
- Focus state uses a blue border and subtle focus emphasis.
- Primary button is visually stronger than the rest of the card.
- Checkbox row sits between password input and primary action.

### Checkbox Behavior

The checkboxes should appear side by side when space allows.

- `记住我`
- `自动登录`

Both are unchecked by default.

In the first version, they are UI state only. They do not need real persistence or auth behavior yet.

### Validation States

- Empty account: `请输入账号`
- Empty password: `请输入密码`

Validation messages should appear near the related fields.

### Submit State

When submitting:

- the primary button enters loading state
- button text can change to `登录中...`
- the card remains visible
- fields and checkboxes may be temporarily disabled

### Failure State

The card should support an inline error banner near the top of the form.

Initial copy options:

- `账号或密码错误，请重试`
- `当前账号未开通访问权限`

The error should be shown inside the card rather than as a global-only notification, because the failure is directly tied to the form.

### Success State

For the first version, success can remain lightweight.

- loading state
- optional text such as `正在进入控制台...`
- route transition into the main application shell

No elaborate success animation is required.

## Responsive Behavior

The page is desktop-first but must remain functional on mobile.

### Desktop

- two-column layout
- left narrative area remains readable and not overcrowded
- right login card stays visually dominant for task completion

### Mobile

- stack vertically
- reduce left-side content to headline + short supporting copy
- keep login card high on the page
- checkbox layout may wrap or stack if horizontal space is tight

## Accessibility And Usability

- Labels must be clearly associated with inputs.
- The tab order should be natural.
- Pressing Enter should submit the form.
- Error feedback must include text, not color alone.
- Checkbox hit areas should be large enough for easy interaction.
- Text/background contrast must remain readable in both normal and error states.

## Technical Integration Boundaries

### Current Scope

The first implementation should include:

- a new dedicated login page route
- the redesigned visual layout
- the account/password form UI
- checkbox UI state
- validation, loading, and inline error placeholders
- a simple success-path transition placeholder

### Future Compatibility

The design should leave room for real authentication later.

Recommended implementation boundaries:

- keep form state local and explicit
- keep submit behavior behind a single handler
- keep error rendering centralized in the login card
- keep post-login navigation separate from form rendering

This ensures the UI-only version can evolve into a real login flow without requiring another layout redesign.

### Future OAuth Compatibility

OAuth is not shown in the first version, but the card should remain extensible.

If OAuth is added later, it can be inserted below the main form area without rewriting the full page architecture.

## Frontend Placement

### Routing

Add a dedicated login route such as `/login`.

The long-term structure should separate:

- login route
- authenticated app route

### App Structure

The current app enters the main layout directly. The revised design assumes a future route split where login is outside the main application shell.

The login page can remain relatively self-contained in the first iteration. Over-componentizing the page is unnecessary unless repeated patterns emerge.

## Content Guidelines

The tone should be primarily Chinese with a small amount of restrained English.

Recommended English usage is limited to lightweight labels such as:

- `Private Preview`

English should not dominate the main narrative or action labels.

## Acceptance Criteria

### Visual

- The page clearly looks more polished than the current login view.
- The layout matches the approved two-column professional structure.
- The color mood is warm and product-oriented rather than cold-admin.
- The login card remains the clearest action area.

### Interaction

- Account and password fields are usable.
- `记住我` and `自动登录` can be toggled.
- Empty fields show validation.
- The login button supports loading state.
- The card supports inline error display.
- A placeholder success flow can enter the main app.

### Responsive

- Desktop layout remains balanced.
- Mobile layout does not break.
- Form controls remain easy to use on small screens.

### Verification

When implementation begins, frontend verification should include at least:

- `npm run lint`
- `npm run build`

## Final Decision

The approved design direction is:

- structure from the professional SaaS mockup
- warmer palette inspired by the career-product mockup
- blue primary action with orange accents
- internal-preview messaging
- account/password only login form
- two checkboxes: `记住我` and `自动登录`

This design should make JobRadar feel like a mature internal job intelligence workspace while keeping implementation scope intentionally small for the first version.
