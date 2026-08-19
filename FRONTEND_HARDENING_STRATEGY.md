# Frontend Hardening Strategy — Roasthyperion

**Goal**: Make the interface resilient to edge cases, errors, internationalization, and real-world usage.

## Hardening Assessment

### 🔴 Critical Hardening Gaps

#### 1. No Error Handling for API Failures
- **Scenario**: Network error, API timeout, 500 error during delete/create
- **Current State**: Button click triggers operation; no error feedback
- **Risk**: Silent failures; users don't know operation failed; potential data inconsistency
- **Impact**: High — Users trust interface without knowing if action succeeded

#### 2. No Duplicate Submission Prevention
- **Scenario**: User clicks delete button 10 times rapidly
- **Current State**: Each click triggers DELETE request; no rate limiting
- **Risk**: Multiple API calls; potential duplicate deletions or race conditions
- **Impact**: High — Could corrupt data or cause server load issues

#### 3. Text Overflow on Long Project Names/Descriptions
- **Scenario**: User creates project with 200-character name
- **Current State**: No text overflow handling; truncation truncates at random points
- **Risk**: Layout breaks; text spills into adjacent elements
- **Impact**: Medium — UI breaks; unreadable content

#### 4. No Empty State on Annotation Search
- **Scenario**: User searches for "xyz" and no annotations match
- **Current State**: List becomes empty; no feedback that search worked
- **Risk**: Users think search is broken
- **Impact**: Medium — Confusing UX

#### 5. No Loading States on Async Operations
- **Scenario**: Slow network; user creates annotation
- **Current State**: Button remains clickable during request
- **Risk**: User clicks multiple times; duplicate submissions
- **Impact**: High — Data consistency risk

#### 6. Missing ARIA Labels on Map Controls
- **Scenario**: Screen reader user opens map
- **Current State**: Basemap selector, opacity slider have no aria-label
- **Risk**: Inaccessible to screen reader users
- **Impact**: Critical — WCAG violation

#### 7. No Internationalization Support
- **Scenario**: User's browser is set to German or French
- **Current State**: All text is hard-coded in English
- **Risk**: Non-English users see English UI
- **Impact**: Medium — Limited market reach

#### 8. Touch Targets Too Small on Mobile
- **Scenario**: User on mobile tries to tap delete icon
- **Current State**: Icon button is ~20px; target too small
- **Risk**: Accidental misclicks; difficult to interact
- **Impact**: High (mobile) — Poor mobile UX

#### 9. No Form Validation Feedback
- **Scenario**: User tries to create annotation with empty title
- **Current State**: Form silently fails or server rejects
- **Risk**: User doesn't know what went wrong
- **Impact**: Medium — Frustrating UX

#### 10. Offline Scenario Not Handled
- **Scenario**: User loses internet connection mid-operation
- **Current State**: Fetch fails silently; no error shown
- **Risk**: Users don't know why action failed
- **Impact**: Medium — Poor error messaging

---

## Hardening Action Plan

### Phase 1: Critical Fixes (A11y + Error Handling)

**Files to modify**:
- `static/js/project_map.js` — Add error handling, ARIA labels, loading states
- `static/css/site.css` — Add loading states, error states, improved overflow handling
- `templates/projects/detail.html` — Add error container

**Changes**:
1. Add `aria-label` to all map controls (basemap select, opacity slider)
2. Add try/catch error handling to all API calls
3. Add loading state feedback (disable buttons, show spinner)
4. Add error message display
5. Add confirmation dialog for destructive actions
6. Prevent duplicate submissions

---

### Phase 2: Text Overflow & Responsive

**Files**:
- `static/css/site.css` — Text overflow classes

**Changes**:
1. Add `.line-clamp` for multi-line truncation
2. Add `.truncate` for single-line ellipsis
3. Ensure flex/grid items don't overflow
4. Use `clamp()` for responsive text sizing

---

### Phase 3: Empty States & Loading States

**Files**:
- `static/js/project_map.js` — Empty state detection
- `static/css/site.css` — Loading skeleton, empty state styling
- `templates/projects/detail.html` — Empty state markup

**Changes**:
1. Show "No annotations matching search" when filtered results empty
2. Add loading skeleton for initial annotation load
3. Improve empty state messaging

---

### Phase 4: Accessibility & i18n

**Files**:
- `static/js/project_map.js` — ARIA live regions, i18n setup
- `static/css/site.css` — RTL support, reduced motion
- Templates — i18n template tags

**Changes**:
1. Add `aria-live` regions for dynamic updates
2. Add `prefers-reduced-motion` media query
3. Prepare for i18n (extract strings)
4. Add RTL support with logical CSS properties

---

## Implementation Details

### 1. API Error Handling Pattern

```javascript
// Current (no error handling):
apiFetch(url, options).then(handleSuccess);

// Hardened:
apiFetch(url, options)
  .then(handleSuccess)
  .catch(error => {
    showErrorMessage(error.message);
    logError(error);
  })
  .finally(resetLoadingState);
```

### 2. Duplicate Submission Prevention

```javascript
// Add to map control initialization
let isProcessing = false;

deleteBtn.addEventListener("click", function (e) {
  if (isProcessing) return; // Prevent double-click
  isProcessing = true;
  deleteBtn.disabled = true;
  
  apiFetch(...).finally(() => {
    isProcessing = false;
    deleteBtn.disabled = false;
  });
});
```

### 3. Loading State Feedback

```css
.btn:disabled,
.btn[aria-busy="true"] {
  opacity: 0.6;
  cursor: not-allowed;
  pointer-events: none;
}

.btn[aria-busy="true"]::after {
  content: "";
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-left: 0.4rem;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
```

### 4. Text Overflow Handling

```css
/* Card description truncation */
.card p {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Annotation title single-line */
.annotation-popup-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Allow flex items to shrink */
.annotation-list-label {
  min-width: 0; /* Critical for text truncation in flex */
}
```

### 5. Empty State Detection

```javascript
function filterSidebarRows(query) {
  let visibleCount = 0;
  Array.prototype.forEach.call(listContainer.children, function (row) {
    const match = !needle || (row.dataset.title || "").includes(needle);
    row.style.display = match ? "" : "none";
    if (match) visibleCount++;
  });
  
  // Show "no results" message if all filtered out
  const noResultsMsg = listContainer.parentElement.querySelector('.no-results');
  if (visibleCount === 0 && needle.trim()) {
    if (!noResultsMsg) {
      const msg = document.createElement('div');
      msg.className = 'no-results';
      msg.textContent = 'No annotations matching search';
      listContainer.parentElement.appendChild(msg);
    }
  } else if (noResultsMsg) {
    noResultsMsg.remove();
  }
}
```

### 6. Confirmation Dialog for Destructive Actions

```javascript
function confirmDelete(title) {
  return confirm(`Delete "${title}"? This cannot be undone.`);
}

// In click handler
deleteBtn.addEventListener("click", function () {
  if (!confirmDelete(annotation.title)) return;
  // ... proceed with delete
});
```

### 7. ARIA Labels for Map Controls

```javascript
// Basemap selector
select.setAttribute('aria-label', 'Select basemap layer');

// Opacity slider
input.setAttribute('aria-label', 'Annotation opacity');
input.setAttribute('aria-valuemin', '0');
input.setAttribute('aria-valuemax', '100');
input.setAttribute('aria-valuenow', '100');
// Update aria-valuenow on input
input.addEventListener('input', function() {
  input.setAttribute('aria-valuenow', Math.round(parseFloat(input.value) * 100));
});
```

### 8. Reduced Motion Support

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

### 9. Error Message Container

```html
<!-- Add to detail.html after map -->
<div id="error-container" class="error-container" role="alert" aria-live="polite" aria-atomic="true">
  <!-- Error messages injected here -->
</div>
```

### 10. Form Validation

```javascript
function validateAnnotationForm(title, description) {
  const errors = [];
  if (!title || title.trim() === '') {
    errors.push('Title is required');
  }
  if (title.length > 200) {
    errors.push('Title must be 200 characters or less');
  }
  if (description.length > 1000) {
    errors.push('Description must be 1000 characters or less');
  }
  return errors;
}
```

---

## Testing Checklist

After implementing hardening:

- [ ] **Long Text**: Create annotation with 100+ character title
- [ ] **Empty List**: Delete all annotations; verify empty state shows
- [ ] **Search No Results**: Search for non-existent annotation
- [ ] **Duplicate Submit**: Click delete button 5 times rapidly; verify only one DELETE request
- [ ] **Network Error**: Disable internet; try to create annotation; verify error message
- [ ] **API Error**: Mock 500 error; verify user sees clear error
- [ ] **Slow Network**: Throttle to 3G; verify loading state shows
- [ ] **Screen Reader**: Test with NVDA; all controls should be labeled
- [ ] **Keyboard Only**: Navigate and use app without mouse
- [ ] **Mobile Touch**: Test on actual phone; touch targets >= 44px
- [ ] **Reduced Motion**: Enable in browser; verify animations disabled

---

## Priority & Effort Estimates

| Issue | Priority | Effort | Impact |
|-------|----------|--------|--------|
| API error handling | 🔴 Critical | 3h | High |
| Duplicate submission prevention | 🔴 Critical | 1h | High |
| ARIA labels on map controls | 🔴 Critical | 1h | High |
| Confirmation dialog for delete | 🟠 High | 1h | High |
| Text overflow handling | 🟠 High | 2h | Medium |
| Empty state feedback | 🟠 High | 2h | Medium |
| Loading state indicators | 🟠 High | 2h | Medium |
| Reduced motion support | 🟡 Medium | 1h | Medium |
| Form validation | 🟡 Medium | 2h | Medium |
| Offline error messaging | 🟡 Medium | 1h | Medium |

**Total**: ~16 hours
**Recommended**: Start with 🔴 Critical (5 hours), then proceed to 🟠 High

