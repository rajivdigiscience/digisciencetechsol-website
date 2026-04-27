const menuToggle = document.getElementById('menuToggle');
const navLinks = document.getElementById('navLinks');
const contactForm = document.getElementById('contactForm');
const formNote = document.getElementById('formNote');
const serviceSelect = document.getElementById('service');
const submitButton = contactForm ? contactForm.querySelector('button[type="submit"]') : null;
const appConfig = window.DIGISCIENCE_CONFIG || {};

if (menuToggle && navLinks) {
  menuToggle.addEventListener('click', () => {
    const isOpen = navLinks.classList.toggle('open');
    menuToggle.setAttribute('aria-expanded', String(isOpen));
  });

  navLinks.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      navLinks.classList.remove('open');
      menuToggle.setAttribute('aria-expanded', 'false');
    });
  });
}

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  },
  { threshold: 0.12 }
);

document.querySelectorAll('.reveal').forEach((element) => observer.observe(element));

document.querySelectorAll('.faq-item').forEach((item) => {
  const button = item.querySelector('.faq-question');
  const indicator = button ? button.querySelector('span') : null;
  if (!button) return;

  const syncFaqState = () => {
    const open = item.classList.contains('open');
    button.setAttribute('aria-expanded', String(open));
    if (indicator) indicator.textContent = open ? '−' : '+';
  };

  syncFaqState();

  button.addEventListener('click', () => {
    item.classList.toggle('open');
    syncFaqState();
  });
});

document.querySelectorAll('[data-service]').forEach((link) => {
  link.addEventListener('click', () => {
    const service = link.getAttribute('data-service');
    if (serviceSelect && service) {
      serviceSelect.value = service;
    }
  });
});

if (contactForm && formNote) {
  const showFormNote = (message, kind = 'info') => {
    formNote.innerHTML = message;
    formNote.classList.remove('is-success', 'is-info');
    formNote.classList.add(kind === 'success' ? 'is-success' : 'is-info', 'show');
  };

  const setSubmitting = (submitting) => {
    if (!submitButton) return;
    submitButton.disabled = submitting;
    submitButton.textContent = submitting ? 'Submitting...' : 'Submit Enquiry';
  };

  const isValidEmail = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

  contactForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    if (!contactForm.reportValidity()) {
      showFormNote('Please complete the required fields and then submit your enquiry again.');
      return;
    }

    const payload = {
      name: contactForm.name.value.trim(),
      email: contactForm.email.value.trim(),
      company: contactForm.company.value.trim(),
      service: contactForm.service.value,
      message: contactForm.message.value.trim(),
      website: contactForm.website.value.trim(),
      source: window.location.hostname || 'website',
      submittedAt: new Date().toISOString()
    };

    if (!payload.name || !payload.email || !payload.message) {
      showFormNote('Please complete your name, email, and requirement before submitting.');
      return;
    }

    if (!isValidEmail(payload.email)) {
      showFormNote('Please enter a valid email address and submit your enquiry again.');
      contactForm.email.focus();
      return;
    }

    const leadEndpointUrl = appConfig.leadEndpointUrl || appConfig.googleScriptUrl || '';

    if (!leadEndpointUrl || leadEndpointUrl.includes('PASTE_YOUR')) {
      showFormNote('The enquiry service is temporarily unavailable. Please try again shortly or email <a href="mailto:rajiv.gupta@digisciencetechsol.com">rajiv.gupta@digisciencetechsol.com</a> directly.');
      return;
    }

    if (leadEndpointUrl.includes('/macros/library/')) {
      showFormNote('The enquiry service is temporarily unavailable. Please try again shortly or email <a href="mailto:rajiv.gupta@digisciencetechsol.com">rajiv.gupta@digisciencetechsol.com</a> directly.');
      return;
    }

    const isGoogleScriptEndpoint = /script\.google\.com\/macros\/s\/.+\/exec/.test(leadEndpointUrl);
    const isDigiscienceLeadEndpoint = /n8n\.digisciencetechsol\.com\/webhook\/digiscience-lead-/.test(leadEndpointUrl);
    if (!isGoogleScriptEndpoint && !isDigiscienceLeadEndpoint) {
      showFormNote('The enquiry service is temporarily unavailable. Please try again shortly or email <a href="mailto:rajiv.gupta@digisciencetechsol.com">rajiv.gupta@digisciencetechsol.com</a> directly.');
      return;
    }

    try {
      setSubmitting(true);
      showFormNote('Submitting your enquiry securely. Please wait...');

      const body = new URLSearchParams(payload);
      await fetch(leadEndpointUrl, {
        method: 'POST',
        mode: 'no-cors',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
        },
        body: body.toString()
      });

      if (typeof window.gtag === 'function') {
        window.gtag('event', 'generate_lead', {
          event_category: 'engagement',
          event_label: payload.service || 'Website enquiry'
        });
      }

      contactForm.reset();
      showFormNote('Your enquiry has been submitted successfully. Redirecting...', 'success');
      window.setTimeout(() => {
        window.location.href = 'success.html';
      }, 700);
    } catch (error) {
      console.error(error);
      showFormNote('We could not submit your enquiry right now. Please try again, or email <a href="mailto:rajiv.gupta@digisciencetechsol.com">rajiv.gupta@digisciencetechsol.com</a> directly.');
    } finally {
      setSubmitting(false);
    }
  });
}
