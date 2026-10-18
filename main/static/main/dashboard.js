(() => {
  const root = document.documentElement;
  const status = document.getElementById('status');
  const runButton = document.getElementById('run');
  const animatedGroups = ['.summary article', '.tier', '.panel', '.risk article', '.bar i'];
  const charts = [...document.querySelectorAll('.chart')];

  const savedTheme = window.localStorage.getItem('money-maxxer-theme');
  if (savedTheme === 'light' || savedTheme === 'dark') root.dataset.theme = savedTheme;

  // Graphs animate only after they enter the user's viewport.
  const chartObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) entry.target.classList.add('is-visible');
    });
  }, { threshold: 0.28 });
  charts.forEach((chart) => chartObserver.observe(chart));

  document.querySelectorAll('[data-theme]').forEach((button) => {
    button.classList.toggle('selected', button.dataset.theme === root.dataset.theme);
    button.addEventListener('click', () => {
      if (button.dataset.theme === root.dataset.theme) return;
      window.localStorage.setItem('money-maxxer-theme', button.dataset.theme);
      window.location.reload();
    });
  });

  function animateNumbers() {
    document.querySelectorAll('.summary article b').forEach((element) => {
      const original = element.dataset.value || element.textContent;
      if (!element.dataset.value) element.dataset.value = original;
      const numeric = Number(original.replace(/[^0-9.]/g, ''));
      if (!Number.isFinite(numeric)) return;
      const prefix = original.trim().startsWith('$') ? '$' : '';
      const suffix = original.includes('×') ? '×' : '';
      const decimals = original.includes('.') ? 2 : 0;
      const started = performance.now();
      const tick = (now) => {
        const progress = Math.min((now - started) / 850, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        element.textContent = `${prefix}${(numeric * eased).toLocaleString(undefined, { maximumFractionDigits: decimals })}${suffix}`;
        if (progress < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  }

  function replayMotion() {
    animatedGroups.forEach((selector) => document.querySelectorAll(selector).forEach((item) => {
      item.style.animation = 'none';
      void item.offsetWidth;
      item.style.animation = '';
    }));
    charts.forEach((chart) => {
      if (!chart.classList.contains('is-visible')) return;
      chart.classList.remove('is-visible');
      void chart.offsetWidth;
      chart.classList.add('is-visible');
    });
    animateNumbers();
  }

  runButton.addEventListener('click', () => {
    const date = document.getElementById('date').value.trim() || 'the selected period';
    runButton.classList.add('is-running');
    status.textContent = `Refreshing simulation for ${date}…`;
    replayMotion();
    window.setTimeout(() => {
      runButton.classList.remove('is-running');
      status.textContent = `Simulation refreshed for ${date}.`;
    }, 1100);
  });

  const csvInput = document.getElementById('csv');
  csvInput.addEventListener('change', (event) => {
    const files = [...event.target.files];
    if (!files.length) return;
    if (files.length > 2) {
      status.textContent = 'Select up to two CSV files. Choose two together to compare them side by side.';
      return;
    }
    const names = files.map((file) => file.name).join(' and ');
    const fileLabel = files.length === 1
      ? `${names} selected. To compare allocations, select a second CSV too.`
      : `${names} selected. Click Run to compare both allocations side by side.`;
    status.textContent = fileLabel;
    if (files.length === 1) {
      const reader = new FileReader();
      reader.onload = () => {
        const lines = String(reader.result).split(/\r?\n/).filter(Boolean);
        status.textContent = `${names} loaded · ${Math.max(lines.length - 1, 0)} data rows. Select a second CSV to compare.`;
        replayMotion();
      };
      reader.onerror = () => { status.textContent = 'Could not read that CSV file.'; };
      reader.readAsText(files[0]);
    }
  });

  document.getElementById('csv-upload-form').addEventListener('submit', (event) => {
    if (csvInput.files.length > 2) {
      event.preventDefault();
      status.textContent = 'Select no more than two CSV files.';
    }
  });

  animateNumbers();
})();
