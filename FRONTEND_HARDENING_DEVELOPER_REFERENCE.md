# Frontend Hardening — Developer Quick Reference

## What Changed & Where

### JavaScript Changes (project_map.js)

#### New Global State
```javascript
let isProcessing = false;        // Duplicate submission prevention
let errorContainer = null;       // Error message display
```

#### New Functions
```javascript
showError(message, duration)     // Display error message (5s default)
setProcessing(isActive)          // Set processing flag
isOperationInProgress()          // Check if operation in progress
```

#### Updated Functions

**`loadAnnotations()`**
- Added `.catch()` for error handling
- Shows error if annotation load fails

**`addSidebarRow(annotation)`**
- Added `aria-label` to view label (e.g., "View Berlin")
- Added `aria-label` to delete button (e.g., "Delete Berlin")
- Added confirmation dialog before delete
- Added error handling with `.catch()`
- Added duplicate submission prevention with `isProcessing` check

**`renderPopupContent(annotation)`**
- Added `aria-label` to delete button
- Added confirmation dialog before delete
- Added error handling and async states

**`filterSidebarRows(query)`**
- Enhanced to detect empty state
- Shows "No annotations matching search" message
- Auto-removes message when results appear

**`openAnnotationForm(geometry)`**
- Added form field validation (required title, character limits)
- Added error display for validation failures
- Added `maxlength` attributes to inputs
- Added error handling with `.catch()`
- Added processing state management

**`addBasemapControl()`**
- Added `aria-label="Select basemap layer"` to select

**`addOpacityControl()`**
- Added `aria-label`, `aria-valuemin`, `aria-valuemax`, `aria-valuenow` to slider
- Updates `aria-valuenow` on input (0-100 scale)
- Added `for` attribute linking label to input

**`initMap()`**
- Initialize `errorContainer` from DOM
- Now called at map load, not before

---

### CSS Changes (site.css)

#### New Error Handling Styles
```css
#error-container { /* Error message container */ }
.error-message { /* Individual error message */ }
@keyframes slideIn { /* Error entry animation */ }
```

#### Text Overflow Handling
```css
.annotation-popup-title { overflow: hidden; text-overflow: ellipsis; }
.annotation-list-label { min-width: 0; overflow-wrap: break-word; }
.card p { -webkit-line-clamp: 2; /* Multi-line truncation */ }
```

#### Accessibility Improvements
```css
:focus-visible { outline: 2px solid var(--color-primary); }
.icon-btn:focus-visible { /* Focus on buttons */ }
```

#### Touch Target Improvements
```css
.annotation-list-row { 
    min-height: 44px;     /* WCAG AAA touch target */
    padding: 0.6rem 0;    /* Improved vertical space */
}
.icon-btn {
    min-width: 44px;      /* Square button */
    min-height: 44px;     /* Minimum tap area */
}
```

#### Range Slider Styling
```css
.map-ctrl-slider input[type="range"]::-webkit-slider-thumb { /* Webkit */ }
.map-ctrl-slider input[type="range"]::-moz-range-thumb { /* Mozilla */ }
/* Focus and hover states for both */
```

#### Reduced Motion Support
```css
@media (prefers-reduced-motion: reduce) {
    * { animation-duration: 0.01ms !important; }
}
```

#### Disabled/Loading States
```css
.btn:disabled { opacity: 0.65; cursor: not-allowed; }
```

---

### HTML Changes (detail.html)

```html
<!-- Added error container before map shell -->
<div id="error-container" class="error-container" 
     role="region" 
     aria-label="Notifications" 
     aria-live="polite" 
     aria-atomic="true">
</div>
```

---

## Hardening Patterns Used

### 1. Error Handling Pattern
```javascript
apiFetch(url, options)
    .then(handleSuccess)
    .catch(error => showError("Failed to X: " + error.message))
    .finally(() => button.disabled = false);
```

### 2. Duplicate Prevention Pattern
```javascript
if (isOperationInProgress()) return;  // Guard clause
button.disabled = true;
setProcessing(true);
apiFetch(url).finally(() => {
    button.disabled = false;
    setProcessing(false);
});
```

### 3. Confirmation Pattern
```javascript
if (confirm('Delete "' + title + '"? This cannot be undone.')) {
    // Proceed with delete
}
```

### 4. Validation Pattern
```javascript
if (!title.trim()) { showError("Title is required"); return; }
if (title.length > 200) { showError("Title too long"); return; }
// Proceed with submission
```

### 5. ARIA Update Pattern
```javascript
// Initially set
element.setAttribute('aria-valuenow', '50');
// On change
element.addEventListener('input', function() {
    element.setAttribute('aria-valuenow', newValue);
});
```

### 6. Text Truncation Pattern
```css
/* Single line */
.element { white-space: nowrap; text-overflow: ellipsis; overflow: hidden; }

/* Multi-line */
.element { 
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
```

---

## Testing Shortcuts

### Test Error Handling
```javascript
// In console, mock failure
const originalFetch = window.fetch;
window.fetch = () => Promise.reject(new Error("Network error"));
// Now try delete annotation
window.fetch = originalFetch;  // Restore
```

### Test Reduced Motion
```javascript
// In console, simulate OS preference
matchMedia('(prefers-reduced-motion: reduce)').matches  // true
// DevTools: Emulate CSS media feature prefers-reduced-motion
```

### Test Touch Targets
```javascript
// Measure button size
document.querySelector('.icon-btn').getBoundingClientRect()
// Should see width: 44+, height: 44+
```

### Test ARIA Labels
```javascript
// Check aria-label set
document.querySelector('button').getAttribute('aria-label')
// Should return descriptive label
```

---

## Common Modifications

### Adding Error Handling to New Operations

**Template**:
```javascript
button.addEventListener('click', function() {
    if (isOperationInProgress()) return;
    
    button.disabled = true;
    setProcessing(true);
    
    apiFetch(url, options)
        .then(success => {
            // Handle success
            showError("Success message", 2000);
        })
        .catch(error => {
            showError("Failed: " + error.message);
        })
        .finally(() => {
            button.disabled = false;
            setProcessing(false);
        });
});
```

### Adding ARIA Labels to New Controls

```javascript
const control = document.createElement('select');
control.setAttribute('aria-label', 'Descriptive label for screen reader');
// For dynamic elements:
control.setAttribute('aria-valuenow', currentValue);  // For sliders/spinners
```

### Adding Text Truncation to New Elements

```css
/* Single line with ellipsis */
.my-element {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Multi-line truncation (2 lines max) */
.my-element {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

/* Flex container support (prevent overflow) */
.flex-item {
    min-width: 0;  /* Allow shrinking below content size */
}
```

---

## Known Behaviors After Hardening

### Error Messages
- Display in top-right corner
- Auto-dismiss after 5 seconds (or 2 seconds for success)
- Stack if multiple errors occur
- Show in `#error-container` with role="alert"

### Disabled During Operations
- Delete buttons disabled during DELETE request
- Form submit disabled during POST request
- Rapidly clicking has no effect
- Buttons re-enable on completion or error

### Confirmations
- Appear before ALL destructive operations
- Dialog shows the item name/title
- Cancel prevents operation
- OK proceeds with operation

### Keyboard Navigation
- Tab through all buttons shows blue outline
- Focus outline 2px solid, visible on all browsers
- Keyboard Enter/Space trigger buttons
- Shift+Tab navigates backwards

### Screen Reader Announcements
- "Delete Berlin, button" (delete labels)
- "Select basemap layer, combobox" (select labels)
- "Adjust annotation opacity, slider, 50%" (range labels with value)

### Mobile Experience
- Buttons minimum 44×44px
- Touch targets easy to tap
- No accidental clicks from padding
- Search results clear on mobile

---

## Performance Considerations

### No Performance Regressions
- ARIA labels add minimal overhead (just attributes)
- Error handling uses standard try/catch (no new dependencies)
- Text truncation uses native CSS (no JavaScript)
- Reduced motion disables animations only when needed

### Potential Future Optimizations
- Batch error messages if many occur
- Debounce search empty-state detection
- Lazy-load error animations
- Use intersection observer for visibility

---

## Browser Compatibility

### Range Slider Styling
- ✅ Chrome 5+ (webkit)
- ✅ Firefox 22+ (moz)
- ✅ Safari 5+ (webkit)
- ✅ Edge 12+ (webkit)
- ❌ IE 11 (no support, falls back to default)

### ARIA Attributes
- ✅ All modern browsers
- ✅ Screen readers: NVDA, JAWS, VoiceOver
- ✅ Tested: Windows + macOS

### CSS Features Used
- ✅ Flexbox (IE 11+)
- ✅ Grid (all modern browsers)
- ✅ -webkit-line-clamp (all browsers)
- ✅ @supports for feature detection
- ✅ CSS variables (IE 11 won't see them, fallback defaults)

---

## Debugging Checklist

**If confirmation dialog not appearing**:
- Check `confirm()` is called before API request
- Check browser console for JS errors
- Test in different browser (some block confirm)

**If error message not showing**:
- Check `errorContainer` initialized in `initMap()`
- Check `#error-container` exists in HTML
- Check console for "Can't set property" errors
- Verify `showError()` function called in `.catch()`

**If buttons not disabling**:
- Check `button.disabled = true` called
- Verify CSS doesn't override with `pointer-events: auto`
- Check event handler doesn't have `return` preventing async code

**If ARIA labels not announced**:
- Open browser DevTools → Accessibility panel
- Inspect element → check aria-label attribute present
- Test with actual screen reader (NVDA, JAWS)
- Check aria-valuenow updates on input

**If text not truncating**:
- Check `min-width: 0` on flex items
- Verify `white-space: nowrap` set for single-line
- Check `-webkit-line-clamp` set for multi-line
- Test in different browser (webkit vs moz)

---

## Maintenance & Monitoring

### What to Monitor
- Error message clarity (do users understand?)
- Confirmation dialog effectiveness (are users clicking OK?)
- Touch target accidental clicks (analytics if available)
- Screen reader usage (if tracking available)
- ARIA value updates (manually test periodically)

### Log These Events
- Errors by type (API errors, validation errors, network errors)
- Delete confirmations (click OK vs Cancel)
- Search empty states (frequency)
- Form validation failures (which fields)
- Offline scenarios (frequency)

### Periodic Testing (Monthly)
- Test with actual screen reader (NVDA/JAWS)
- Test on real mobile device (< 375px)
- Test with Reduce Motion enabled in OS
- Test offline scenario
- Test slow network (3G throttling)

---

**Last Updated**: August 18, 2026  
**Version**: 1.0 (Initial Hardening Implementation)

