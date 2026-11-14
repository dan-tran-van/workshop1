# FE-04 — Responsive UI & Accessibility

**Scope:** Frontend non-functional and usability testing  
**Priority:** P1  
**Related checklist item:** FE-20

> The checklist defines one formal test case (FE-20). The viewport and accessibility checks below are sub-checks under that case, not additional FE IDs. In the current UI, restaurant details are shown in a panel and analysis is opened from the workspace navigation.

## FE-20 [P1] — Verify responsive layouts, keyboard navigation, and accessible labels

**Type:** Responsive / Accessibility

### Preconditions
- The frontend application is running.
- The restaurant listing, detail, and analysis views are available.
- A browser with developer tools or device emulation is available.

### Test Steps

#### A. Desktop layout — 1440px
1. Set the viewport width to 1440px.
2. Open the restaurant listing page.
3. Select a restaurant and inspect its detail panel.
4. Open the AI analysis dashboard.
5. Inspect the layout and visible controls.

#### B. Tablet layout — 768px
1. Set the viewport width to 768px.
2. Repeat the checks on the listing, selected restaurant detail panel, and analysis view.
3. Inspect navigation, cards, columns, and action controls.

#### C. Mobile layout — 375px
1. Set the viewport width to 375px.
2. Repeat the checks on the listing, selected restaurant detail panel, and analysis view.
3. Inspect text, cards, buttons, and any horizontally arranged content.

#### D. Long review content
1. Select a restaurant containing a long review.
2. Inspect the review at 375px, 768px, and 1440px.
3. Check whether the text can be read without breaking the layout.

#### E. Keyboard navigation
1. Reload the page.
2. Use Tab and Shift+Tab to move through interactive controls.
3. Use Enter or Space to activate applicable controls.
4. Check the visible focus indicator.
5. Check that keyboard focus follows a logical order.

#### F. Accessible labels
1. Inspect search inputs, buttons, and other interactive controls.
2. Verify that each control has an accessible name.
3. Verify that controls can be understood by assistive technology, where tooling is available.

### Expected Results
- The application remains usable at viewport widths of 375px, 768px, and 1440px.
- Content does not unintentionally overflow horizontally.
- Navigation, cards, forms, and action controls adapt to the viewport.
- Long review text wraps or is otherwise presented without breaking the layout.
- Interactive controls can be reached using the keyboard.
- Keyboard focus is visible and follows a logical order.
- Interactive controls have meaningful accessible labels or names.
- Text and controls remain readable and operable at all tested viewport sizes.
- No responsive layout or accessibility issue prevents completion of the main user flow.

---

## Additional exploratory checks

These checks are useful during the pre-demo review but remain part of FE-20 unless the team decides to create separate test IDs:

- Check that dialogs, dropdowns, and menus (if present) can be operated using the keyboard.
- Check that focus is not lost unexpectedly after an action.
- Check that error and empty-state messages are perceivable and understandable.
- Check that buttons are not clipped or too difficult to activate on mobile.
- Check that browser zoom does not make essential controls inaccessible.

## Viewports

| View | Width | Views to check |
|---|---:|---|
| Mobile | 375px | Listing, details panel, analysis |
| Tablet | 768px | Listing, details panel, analysis |
| Desktop | 1440px | Listing, details panel, analysis |
