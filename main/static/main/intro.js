(() => {
  const root = document.documentElement;
  const savedTheme = window.localStorage.getItem('reserve-juggler-theme');
  if (savedTheme === 'light' || savedTheme === 'dark') root.dataset.theme = savedTheme;
  document.querySelectorAll('[data-theme]').forEach((button) => {
    button.classList.toggle('selected', button.dataset.theme === root.dataset.theme);
    button.addEventListener('click', () => {
      if (button.dataset.theme === root.dataset.theme) return;
      window.localStorage.setItem('reserve-juggler-theme', button.dataset.theme);
      window.location.reload();
    });
  });
  const input = document.getElementById('csv');
  const fileName = document.getElementById('file-name');
  const status = document.getElementById('file-status');
  const runLink = document.getElementById('run');
  input.addEventListener('change', () => {
    const file = input.files[0];
    if (!file) return;
    fileName.textContent = file.name;
    const reader = new FileReader();
    reader.onload = () => {
      const rows = String(reader.result).split(/\r?\n/).filter(Boolean).length;
      status.textContent = `${Math.max(rows - 1, 0)} data rows ready to explore.`;
      runLink.classList.remove('disabled');
      runLink.setAttribute('href', runLink.dataset.dashboardUrl || '/overview/');
      runLink.setAttribute('aria-disabled', 'false');
    };
    reader.readAsText(file);
  });
})();
