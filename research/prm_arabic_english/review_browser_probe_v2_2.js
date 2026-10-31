/* WebDriver-injected test instrumentation, never shipped in reviewer packages. */
window.__reviewProbe = {captures: [], downloads: [], errors: []};
window.addEventListener('error', e => window.__reviewProbe.errors.push(e.message));
window.addEventListener('unhandledrejection', e => window.__reviewProbe.errors.push(String(e.reason)));
const makeURL = URL.createObjectURL.bind(URL);
URL.createObjectURL = blob => {
  const url = makeURL(blob);
  blob.text().then(text => window.__reviewProbe.captures.push(JSON.parse(text)));
  return url;
};
// Capture actual browser Blob contents, without an OS download prompt or shared Downloads folder.
const anchorClick = HTMLAnchorElement.prototype.click;
HTMLAnchorElement.prototype.click = function () {
  if (this.download) { window.__reviewProbe.downloads.push(this.download); return; }
  return anchorClick.call(this);
};
window.__reviewMetrics = function () {
  const controls = [...document.querySelectorAll('input,select,textarea,button')];
  const unnamed = controls.filter(e => !(e.textContent.trim() && e.tagName === 'BUTTON') &&
    !e.closest('label') && !e.getAttribute('aria-label') && !e.getAttribute('aria-labelledby') &&
    !document.querySelector('label[for="' + e.id + '"]')).map(e => e.id);
  return {pairs: document.querySelectorAll('.pair').length, candidates: document.querySelectorAll('.candidate').length,
    design_slots: document.querySelectorAll('.slot').length, source_problems: document.querySelectorAll('.problem').length,
    viewport: window.innerWidth, page_width: document.documentElement.scrollWidth, unnamed_controls: unnamed,
    overflow_controls: controls.filter(e=>e.getBoundingClientRect().right>document.documentElement.clientWidth+1).map(e=>e.id),
    nonlocal_page_resources: performance.getEntriesByType('resource').filter(r => !r.name.startsWith('file:') && !r.name.startsWith('blob:')).length,
    csp: document.querySelector('meta[http-equiv="Content-Security-Policy"]').content,
    errors: window.__reviewProbe.errors.slice()};
};
return window.__reviewMetrics();
