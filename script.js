document.getElementById("year").textContent = new Date().getFullYear();

// Provide clear feedback before a real backend is connected.
const contactForm = document.getElementById("contact-form");
const formStatus = document.getElementById("form-status");

contactForm.addEventListener("submit", (event) => {
  event.preventDefault();

  if (!contactForm.checkValidity()) {
    formStatus.textContent = "Please complete every field with a valid email.";
    formStatus.className = "form-status error";
    contactForm.reportValidity();
    return;
  }

  formStatus.textContent = "Thanks! Your message is ready to send.";
  formStatus.className = "form-status success";
  contactForm.reset();
});
