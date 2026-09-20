// Kleine Helfer. Die App funktioniert auch ohne JavaScript.
document.addEventListener('click', (event) => {
  const trigger = event.target.closest('[data-confirm]');
  if (trigger && !window.confirm(trigger.dataset.confirm)) {
    event.preventDefault();
  }
  const copy = event.target.closest('[data-copy]');
  if (copy) {
    const source = document.querySelector(copy.dataset.copy);
    if (source && navigator.clipboard) {
      navigator.clipboard.writeText(source.innerText).then(() => {
        const label = copy.textContent;
        copy.textContent = 'Kopiert';
        setTimeout(() => { copy.textContent = label; }, 1600);
      });
    }
  }
});

// Aktiven Navigationspunkt anhand des Pfads markieren.
const path = window.location.pathname;
document.querySelectorAll('.topbar nav a').forEach((link) => {
  const href = link.getAttribute('href');
  if (href === path || (href !== '/' && path.startsWith(href))) {
    link.classList.add('active');
  }
});
