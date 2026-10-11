document.documentElement.classList.add('js');
const themeButtons = document.querySelectorAll('[data-set-theme]');
function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  themeButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.setTheme === theme)));
  try { localStorage.setItem('f1-timeline-theme', theme); } catch (_) {}
}
let initialTheme = document.documentElement.dataset.theme || 'auto';
try {
  const savedTheme = localStorage.getItem('f1-timeline-theme');
  if (['light', 'dark', 'auto'].includes(savedTheme)) initialTheme = savedTheme;
} catch (_) {}
setTheme(initialTheme);
themeButtons.forEach(button => button.addEventListener('click', () => setTheme(button.dataset.setTheme)));
const events = [...document.querySelectorAll('.event')];
const filters = [...document.querySelectorAll('[data-filter]')];
function setFilter(value) {
  events.forEach(event => { event.hidden = value !== 'all' && event.dataset[value] !== 'true'; });
  filters.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === value)));
  const count = events.filter(event => !event.hidden).length;
  document.querySelector('#view-count').textContent = `Showing ${count} of ${events.length} identified events · Times in Singapore (UTC+8)`;
}
filters.forEach(button => button.addEventListener('click', () => setFilter(button.dataset.filter)));
function revealTarget() {
  let id; try { id = decodeURIComponent(location.hash.slice(1)); } catch (_) { return; }
  const target = document.getElementById(id);
  if (!target) return;
  const event = target.closest('.event');
  if (event?.hidden) setFilter('all');
  let current = target;
  while (current && current !== document.body) {
    if (current.tagName === 'DETAILS') current.open = true;
    current = current.parentElement;
  }
  document.querySelector('.mobile-jump').open = false;
  requestAnimationFrame(() => target.scrollIntoView({block:'start'}));
}
window.addEventListener('hashchange', revealTarget);
document.querySelectorAll('a[href^="#"]').forEach(a => a.addEventListener('click', () => {
  if (a.hash === location.hash) revealTarget();
}));
if (location.hash) revealTarget();
document.querySelectorAll('video').forEach(video => {
  video.addEventListener('play', () => {
    document.querySelectorAll('video').forEach(other => { if (other !== video) other.pause(); });
    video.dataset.playing = 'true';
  });
  video.addEventListener('error', () => {
    const message = video.closest('figure').querySelector('.video-error');
    if (message) message.hidden = false;
  });
});
document.querySelectorAll('details').forEach(details => details.addEventListener('toggle', () => {
  if (!details.open) details.querySelectorAll('video').forEach(video => video.pause());
}));
