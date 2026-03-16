// Portfolio main script — smooth interactions
document.addEventListener('DOMContentLoaded', () => {
  // Intersection observer for fade-in on scroll
  const cards = document.querySelectorAll('.project-card');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.style.opacity = '1';
        e.target.style.transform = 'translateY(0)';
      }
    });
  }, { threshold: 0.1 });
  cards.forEach(card => observer.observe(card));
});
