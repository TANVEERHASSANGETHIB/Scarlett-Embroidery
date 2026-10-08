document.querySelectorAll('[data-service-hero]').forEach((form) => {
  const service = form.querySelector('[name="service"]');
  const update = () => {
    const patches = service.value === 'patches';
    form.querySelectorAll('[data-comparison-only]').forEach((section) => {
      section.hidden = patches;
      section.querySelectorAll('input').forEach((input) => { input.disabled = patches; });
    });
    form.querySelector('[data-hero-photo-label]').textContent = patches ? 'Hero photo' : 'Before photo';
    form.querySelector('[data-hero-save]').textContent = patches ? 'Save hero photo' : 'Save before / after';
  };
  service.addEventListener('change', update);
  update();
});
